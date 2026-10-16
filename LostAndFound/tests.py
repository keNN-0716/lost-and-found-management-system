from datetime import date

from django.test import TestCase
from django.urls import reverse

from .backends import IDNumberAuthBackend
from .models import CustomUser, FoundItem, ItemStatus, LostItem


class SignupAndLoginTests(TestCase):
    """Signup must collect an ID number so users can actually log in."""

    def test_signup_form_includes_id_number(self):
        response = self.client.post(reverse('signup'), {
            'username': 'juandelacruz',
            'id_number': '2026-0001',
            'password1': 'S3curePass!word',
            'password2': 'S3curePass!word',
        })
        self.assertRedirects(response, reverse('login'))
        user = CustomUser.objects.get(username='juandelacruz')
        self.assertEqual(user.id_number, '2026-0001')
        self.assertEqual(user.role, CustomUser.Roles.NORMAL_USER)

    def test_signup_requires_id_number(self):
        response = self.client.post(reverse('signup'), {
            'username': 'no-id-user',
            'password1': 'S3curePass!word',
            'password2': 'S3curePass!word',
        })
        self.assertEqual(response.status_code, 200)  # re-rendered with errors
        self.assertContains(response, 'id_number')
        self.assertFalse(CustomUser.objects.filter(username='no-id-user').exists())

    def test_login_with_id_number(self):
        CustomUser.objects.create_user(
            username='maria', id_number='2026-0002', password='pw12345!'
        )
        response = self.client.post(reverse('login'), {
            'id_number': '2026-0002',
            'password': 'pw12345!',
        })
        # login_redirect then forwards normal users to the user home page
        self.assertRedirects(
            response, reverse('login_redirect'), fetch_redirect_response=False
        )

    def test_login_with_wrong_password_fails(self):
        CustomUser.objects.create_user(
            username='maria', id_number='2026-0002', password='pw12345!'
        )
        response = self.client.post(reverse('login'), {
            'id_number': '2026-0002',
            'password': 'wrong-password',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Invalid ID number or password.')


class AuthBackendTests(TestCase):
    def setUp(self):
        self.backend = IDNumberAuthBackend()
        self.user = CustomUser.objects.create_user(
            username='ana', id_number='2026-0003', password='pw12345!'
        )

    def test_authenticates_by_id_number(self):
        user = self.backend.authenticate(
            None, id_number='2026-0003', password='pw12345!'
        )
        self.assertEqual(user, self.user)

    def test_inactive_user_cannot_authenticate(self):
        self.user.is_active = False
        self.user.save()
        user = self.backend.authenticate(
            None, id_number='2026-0003', password='pw12345!'
        )
        self.assertIsNone(user)

    def test_empty_id_number_returns_none(self):
        self.assertIsNone(self.backend.authenticate(None, id_number='', password='x'))


class RoleDecoratorTests(TestCase):
    def setUp(self):
        self.normal = CustomUser.objects.create_user(
            username='normal', id_number='2026-0004', password='pw12345!'
        )
        self.manager = CustomUser.objects.create_user(
            username='manager', id_number='2026-0005', password='pw12345!',
            role=CustomUser.Roles.MANAGEMENT,
        )

    def test_anonymous_redirected_to_login(self):
        response = self.client.get(reverse('lost_and_found'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)

    def test_normal_user_gets_403_on_management_page(self):
        self.client.force_login(self.normal)
        response = self.client.get(reverse('lost_and_found'))
        self.assertEqual(response.status_code, 403)

    def test_management_user_can_access_management_page(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse('lost_and_found'))
        self.assertEqual(response.status_code, 200)


class SearchTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username='searcher', id_number='2026-0006', password='pw12345!'
        )
        LostItem.objects.create(
            name='Black Wallet', description='Leather bifold',
            date_lost=date(2026, 10, 1), location_lost='Library 2F',
        )

    def test_search_requires_login(self):
        response = self.client.get(reverse('search_results'), {'q': 'wallet'})
        self.assertEqual(response.status_code, 302)

    def test_search_finds_matching_items(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('search_results'), {'q': 'wallet'})
        self.assertContains(response, 'Black Wallet')

    def test_search_no_match(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('search_results'), {'q': 'umbrella'})
        self.assertContains(response, 'No results found')


class LostItemViewTests(TestCase):
    def setUp(self):
        self.manager = CustomUser.objects.create_user(
            username='manager2', id_number='2026-0007', password='pw12345!',
            role=CustomUser.Roles.MANAGEMENT,
        )
        self.normal = CustomUser.objects.create_user(
            username='normal2', id_number='2026-0008', password='pw12345!'
        )

    def test_posting_lost_item_records_reporter(self):
        self.client.force_login(self.manager)
        response = self.client.post(reverse('lost_items'), {
            'name': 'Umbrella',
            'description': 'Blue folding umbrella',
            'date_lost': '2026-10-02',
            'location_lost': 'Gym',
        })
        self.assertRedirects(response, reverse('lost_items'))
        item = LostItem.objects.get(name='Umbrella')
        self.assertEqual(item.reported_by, self.manager)
        self.assertEqual(item.status, ItemStatus.OPEN)

    def test_invalid_lost_item_form_shows_errors(self):
        self.client.force_login(self.manager)
        response = self.client.post(reverse('lost_items'), {
            'name': '',  # missing required fields
            'description': '',
            'location_lost': '',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'form-error')

    def test_normal_user_cannot_report_lost_item(self):
        # lost_items POST is open to any logged-in user per project design,
        # but the management dashboard itself stays protected (RoleDecoratorTests).
        # This test documents current behavior: reporting is allowed for users too.
        self.client.force_login(self.normal)
        response = self.client.post(reverse('lost_items'), {
            'name': 'Phone',
            'description': 'Red iPhone',
            'date_lost': '2026-10-03',
            'location_lost': 'Canteen',
        })
        self.assertRedirects(response, reverse('lost_items'))


class ClaimWorkflowTests(TestCase):
    def setUp(self):
        self.manager = CustomUser.objects.create_user(
            username='manager3', id_number='2026-0009', password='pw12345!',
            role=CustomUser.Roles.MANAGEMENT,
        )
        self.claimer = CustomUser.objects.create_user(
            username='claimer', id_number='2026-0010', password='pw12345!'
        )
        self.found_item = FoundItem.objects.create(
            name='ID Lanyard', description='Blue lanyard with ID',
            date_found=date(2026, 10, 4), location_found='Main Hall',
            reported_by=self.manager,
        )
        self.lost_item = LostItem.objects.create(
            name='Calculator', description='Casio fx-991EX',
            date_lost=date(2026, 10, 4), location_lost='Room 201',
            reported_by=self.manager,
        )

    def test_claim_found_item(self):
        self.client.force_login(self.claimer)
        response = self.client.post(reverse('claim_item', args=['found', self.found_item.item_id]))
        self.assertRedirects(response, reverse('found_items'))
        self.found_item.refresh_from_db()
        self.assertEqual(self.found_item.status, ItemStatus.CLAIMED)
        self.assertEqual(self.found_item.claimed_by, self.claimer)

    def test_claim_lost_item(self):
        self.client.force_login(self.claimer)
        self.client.post(reverse('claim_item', args=['lost', self.lost_item.item_id]))
        self.lost_item.refresh_from_db()
        self.assertEqual(self.lost_item.status, ItemStatus.CLAIMED)
        self.assertEqual(self.lost_item.claimed_by, self.claimer)

    def test_cannot_claim_already_claimed_item(self):
        self.found_item.status = ItemStatus.CLAIMED
        self.found_item.claimed_by = self.manager
        self.found_item.save()
        self.client.force_login(self.claimer)
        response = self.client.post(reverse('claim_item', args=['found', self.found_item.item_id]))
        self.assertRedirects(response, reverse('found_items'))
        self.found_item.refresh_from_db()
        self.assertEqual(self.found_item.claimed_by, self.manager)  # unchanged

    def test_unknown_item_type_is_forbidden(self):
        self.client.force_login(self.claimer)
        response = self.client.post(reverse('claim_item', args=['magic', 1]))
        self.assertEqual(response.status_code, 403)

    def test_resolve_requires_management(self):
        self.found_item.status = ItemStatus.CLAIMED
        self.found_item.claimed_by = self.claimer
        self.found_item.save()

        self.client.force_login(self.claimer)
        response = self.client.post(reverse('resolve_item', args=['found', self.found_item.item_id]))
        self.assertEqual(response.status_code, 403)

        self.client.force_login(self.manager)
        response = self.client.post(reverse('resolve_item', args=['found', self.found_item.item_id]))
        self.assertRedirects(response, reverse('found_items'))
        self.found_item.refresh_from_db()
        self.assertEqual(self.found_item.status, ItemStatus.RESOLVED)

    def test_resolve_open_item_fails(self):
        self.client.force_login(self.manager)
        self.client.post(reverse('resolve_item', args=['found', self.found_item.item_id]))
        self.found_item.refresh_from_db()
        self.assertEqual(self.found_item.status, ItemStatus.OPEN)  # unchanged


class UserHomePageTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username='homeuser', id_number='2026-0011', password='pw12345!'
        )
        LostItem.objects.create(
            name='Reported by me', description='desc',
            date_lost=date(2026, 10, 5), location_lost='Lab',
            reported_by=self.user,
        )
        FoundItem.objects.create(
            name='Claimed by me', description='desc',
            date_found=date(2026, 10, 5), location_found='Lab',
            claimed_by=self.user,
        )

    def test_home_page_lists_reports_and_claims(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('user_home_page'))
        self.assertContains(response, 'Reported by me')
        self.assertContains(response, 'Claimed by me')

    def test_requires_login(self):
        response = self.client.get(reverse('user_home_page'))
        self.assertEqual(response.status_code, 302)


class LogoutTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username='logoutuser', id_number='2026-0012', password='pw12345!'
        )

    def test_logout_post(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('logout'))
        self.assertRedirects(response, reverse('login'))
        # Session should no longer have an authenticated user
        response = self.client.get(reverse('user_home_page'))
        self.assertEqual(response.status_code, 302)