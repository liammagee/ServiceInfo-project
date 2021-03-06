from datetime import time
from http.client import OK, BAD_REQUEST
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth import authenticate
from django.core.urlresolvers import reverse
from django.test import TestCase
import xlwt

from email_user.tests.factories import EmailUserFactory
from services.import_export import validate_and_import_data, get_export_workbook, PROVIDER_HEADINGS, \
    PROVIDER_SHEET_NAME, SERVICES_SHEET_NAME, SELECTION_CRITERIA_SHEET_NAME, add_models_to_sheet, \
    SERVICE_HEADINGS, SELECTION_CRITERIA_HEADINGS
from services.models import Provider, Service, SelectionCriterion
from services.tests.factories import ProviderFactory, ProviderTypeFactory, ServiceFactory, \
    ServiceTypeFactory, ServiceAreaFactory, SelectionCriterionFactory
from services.tests.test_api import APITestMixin
from services.tests.test_export import get_book_bits


VERY_LONG_STRING = 'x' * 1024


def make_empty_book():
    """
    Return an xlwt Workbook object with our sheets & column
    headings, but no data.
    :return: an xlwt Workbook object
    """
    return get_export_workbook([])


class ValidateImportTest(TestCase):
    def setUp(self):
        self.user = EmailUserFactory()

    def test_not_spreadsheet(self):
        errs = validate_and_import_data(self.user, b'I am not a spreadsheet')
        self.assertTrue(errs)

    def test_too_few_sheets(self):
        xlwt_book = xlwt.Workbook(encoding='utf-8')
        xlwt_book.add_sheet(PROVIDER_SHEET_NAME)
        xlwt_book.add_sheet(SERVICES_SHEET_NAME)
        errs = validate_and_import_data(self.user, get_book_bits(xlwt_book))
        self.assertTrue(errs)

    def test_too_many_sheets(self):
        xlwt_book = xlwt.Workbook(encoding='utf-8')
        xlwt_book.add_sheet(PROVIDER_SHEET_NAME)
        xlwt_book.add_sheet(SERVICES_SHEET_NAME)
        xlwt_book.add_sheet(PROVIDER_SHEET_NAME + 'b')
        xlwt_book.add_sheet(SERVICES_SHEET_NAME + 'b')
        errs = validate_and_import_data(self.user, get_book_bits(xlwt_book))
        self.assertTrue(errs)

    def test_empty_book(self):
        # A book with just 3 empty sheets should not validate
        xlwt_book = xlwt.Workbook(encoding='utf-8')
        xlwt_book.add_sheet('x' + PROVIDER_SHEET_NAME)
        xlwt_book.add_sheet(SERVICES_SHEET_NAME)
        xlwt_book.add_sheet(SELECTION_CRITERIA_SHEET_NAME)
        errs = validate_and_import_data(self.user, get_book_bits(xlwt_book))
        self.assertTrue(errs)

    def test_headers_only_book(self):
        # An book with only headers should validate
        xlwt_book = make_empty_book()
        errs = validate_and_import_data(self.user, get_book_bits(xlwt_book))
        self.assertFalse(errs)

    def test_bad_provider_headers(self):
        with patch('services.import_export.PROVIDER_HEADINGS') as headings:
            headings[:] = ['foo', 'bar']
            xlwt_book = make_empty_book()
        errs = validate_and_import_data(self.user, get_book_bits(xlwt_book))
        self.assertTrue(errs)

    def test_bad_service_headers(self):
        with patch('services.import_export.SERVICE_HEADINGS') as headings:
            headings[:] = ['foo', 'bar']
            xlwt_book = make_empty_book()
        errs = validate_and_import_data(self.user, get_book_bits(xlwt_book))
        self.assertTrue(errs)

    def test_bad_criteria_headers(self):
        with patch('services.import_export.SELECTION_CRITERIA_HEADINGS') as headings:
            headings[:] = ['foo', 'bar']
            xlwt_book = make_empty_book()
        errs = validate_and_import_data(self.user, get_book_bits(xlwt_book))
        self.assertTrue(errs)

    def test_bad_provider_sheet_name(self):
        # Wrong sheet name should not validate
        xlwt_book = xlwt.Workbook(encoding='utf-8')
        provider_sheet = xlwt_book.add_sheet('x' + PROVIDER_SHEET_NAME)
        add_models_to_sheet(provider_sheet, PROVIDER_HEADINGS, [])
        service_sheet = xlwt_book.add_sheet(SERVICES_SHEET_NAME)
        add_models_to_sheet(service_sheet, SERVICE_HEADINGS, [])
        criteria_sheet = xlwt_book.add_sheet(SELECTION_CRITERIA_SHEET_NAME)
        add_models_to_sheet(criteria_sheet, SELECTION_CRITERIA_HEADINGS, [])
        errs = validate_and_import_data(self.user, get_book_bits(xlwt_book))
        self.assertTrue(errs)

    def test_bad_services_sheet_name(self):
        # Wrong sheet name should not validate
        xlwt_book = xlwt.Workbook(encoding='utf-8')
        provider_sheet = xlwt_book.add_sheet(PROVIDER_SHEET_NAME)
        add_models_to_sheet(provider_sheet, PROVIDER_HEADINGS, [])
        service_sheet = xlwt_book.add_sheet('x' + SERVICES_SHEET_NAME)
        add_models_to_sheet(service_sheet, SERVICE_HEADINGS, [])
        criteria_sheet = xlwt_book.add_sheet(SELECTION_CRITERIA_SHEET_NAME)
        add_models_to_sheet(criteria_sheet, SELECTION_CRITERIA_HEADINGS, [])
        errs = validate_and_import_data(self.user, get_book_bits(xlwt_book))
        self.assertTrue(errs)

    def test_bad_criteria_sheet_name(self):
        # Wrong sheet name should not validate
        xlwt_book = xlwt.Workbook(encoding='utf-8')
        provider_sheet = xlwt_book.add_sheet(PROVIDER_SHEET_NAME)
        add_models_to_sheet(provider_sheet, PROVIDER_HEADINGS, [])
        service_sheet = xlwt_book.add_sheet(SERVICES_SHEET_NAME)
        add_models_to_sheet(service_sheet, SERVICE_HEADINGS, [])
        criteria_sheet = xlwt_book.add_sheet('x' + SELECTION_CRITERIA_SHEET_NAME)
        add_models_to_sheet(criteria_sheet, SELECTION_CRITERIA_HEADINGS, [])
        errs = validate_and_import_data(self.user, get_book_bits(xlwt_book))
        self.assertTrue(errs)


def set_cell_value(book, sheet_num, row_num, col_num, value):
    sheet = book.get_sheet(sheet_num)
    sheet.write(r=row_num, c=col_num, label=value)


def blank_out_row_for_testing(book, sheet_num, row_num):
    sheet = book.get_sheet(sheet_num)
    num_cols = sheet.rows[row_num].get_cells_count()
    # We always put the id in the first column, so skip that
    for col in range(1, num_cols):
        sheet.write(r=row_num, c=col, label='')


class ImportWorkbookAPITest(APITestMixin, TestCase):

    def import_book(self, book):
        """
        Given an xlwt Workbook object, call the import API
        and return the response object.
        """
        bits = get_book_bits(book)
        url = reverse('import')
        with BytesIO(bits) as fp:
            fp.name = 'book.xls'
            rsp = self.post_with_token(
                url,
                data={'file': fp},
                format='multipart',
            )
        return rsp

    def test_import_empty_book(self):
        xlwt_book = make_empty_book()
        rsp = self.import_book(xlwt_book)
        self.assertEqual(OK, rsp.status_code, msg=rsp.content.decode('utf-8'))

    def test_provider_add_provider(self):
        type = ProviderTypeFactory()
        provider = ProviderFactory.build(type=type, user=self.user)  # Doesn't save
        self.assertFalse(provider.id)
        book = get_export_workbook([provider])
        rsp = self.import_book(book)
        # self.fail(rsp.content.decode('utf-8'))
        self.assertContains(rsp, "Non-staff users may not create new providers",
                            status_code=BAD_REQUEST)

    def test_staff_add_provider(self):
        type = ProviderTypeFactory()
        self.user.is_staff = True
        self.user.save()
        provider = ProviderFactory.build(type=type, user=self.user)  # Doesn't save
        self.assertFalse(provider.id)
        book = get_export_workbook([provider])
        rsp = self.import_book(book)
        self.assertEqual(OK, rsp.status_code, msg=rsp.content.decode('utf-8'))
        self.assertTrue(Provider.objects.filter(name_en=provider.name_en).exists())

    def test_staff_add_bad_provider(self):
        type = ProviderTypeFactory()
        self.user.is_staff = True
        self.user.save()
        provider = ProviderFactory.build(type=type, user=self.user,
                                         number_of_monthly_beneficiaries=-1)  # Doesn't save
        self.assertFalse(provider.id)
        book = get_export_workbook([provider])
        rsp = self.import_book(book)
        self.assertContains(rsp,
                            "Row 2: number_of_monthly_beneficiaries: Ensure this value is "
                            "greater than or equal to 0.",
                            status_code=BAD_REQUEST)

    def test_staff_add_providers(self):
        # Remember, only one provider per user
        self.user.is_staff = True
        self.user.save()
        type1 = ProviderTypeFactory()
        provider1 = ProviderFactory.build(type=type1, user=self.user)  # Doesn't save
        user2 = EmailUserFactory()
        type2 = ProviderTypeFactory()
        provider2 = ProviderFactory.build(type=type2, user=user2)  # Doesn't save
        book = get_export_workbook([provider1, provider2])
        rsp = self.import_book(book)
        self.assertEqual(OK, rsp.status_code, msg=rsp.content.decode('utf-8'))
        self.assertTrue(Provider.objects.filter(name_en=provider1.name_en).exists())
        self.assertTrue(Provider.objects.filter(name_en=provider2.name_en).exists())

    def test_provider_change_own_data(self):
        # Non-staff can change their own provider
        provider = ProviderFactory(user=self.user)
        # Tweak some data
        provider.name_en = 'Jim-Bob'
        provider.name_ar = 'Ahmed-Bob'
        provider.name_fr = 'Pierre-Bob'
        book = get_export_workbook([provider])
        rsp = self.import_book(book)
        self.assertEqual(OK, rsp.status_code, msg=rsp.content.decode('utf-8'))
        new_provider = Provider.objects.get(id=provider.id)
        self.assertEqual(provider.name_en, new_provider.name_en)
        self.assertEqual(provider.name_ar, new_provider.name_ar)
        self.assertEqual(provider.name_fr, new_provider.name_fr)

    def test_staff_change_provider(self):
        # Staff can change another user's provider
        self.user.is_staff = True
        self.user.save()
        provider = ProviderFactory()
        # Tweak some data
        provider.name_en = 'Jim-Bob'
        provider.name_ar = 'Ahmed-Bob'
        provider.name_fr = 'Pierre-Bob'
        book = get_export_workbook([provider])
        rsp = self.import_book(book)
        self.assertEqual(OK, rsp.status_code, msg=rsp.content.decode('utf-8'))
        new_provider = Provider.objects.get(id=provider.id)
        self.assertEqual(provider.name_en, new_provider.name_en)
        self.assertEqual(provider.name_ar, new_provider.name_ar)
        self.assertEqual(provider.name_fr, new_provider.name_fr)

    def test_staff_change_provider_invalid_id(self):
        self.user.is_staff = True
        self.user.save()
        provider = ProviderFactory()
        # Tweak some data
        provider.name_en = 'Jim-Bob'
        provider.name_ar = 'Ahmed-Bob'
        provider.name_fr = 'Pierre-Bob'
        book = get_export_workbook([provider], cell_overwrite_ok=True)
        sheet = book.get_sheet(0)
        sheet.write(r=1, c=0, label='xyz')
        rsp = self.import_book(book)
        self.assertContains(rsp,
                            "id: xyz is not a valid ID",
                            status_code=BAD_REQUEST,
                            msg_prefix=rsp.content.decode('utf-8'))

    def test_staff_change_nonexistent_provider(self):
        # Staff can change another user's provider
        self.user.is_staff = True
        self.user.save()
        provider = ProviderFactory()
        # Tweak some data
        provider.name_en = 'Jim-Bob'
        provider.name_ar = 'Ahmed-Bob'
        provider.name_fr = 'Pierre-Bob'
        book = get_export_workbook([provider])
        provider_id = provider.id
        provider.delete()
        rsp = self.import_book(book)
        self.assertContains(rsp,
                            "There is no provider with id=%d" % provider_id,
                            status_code=BAD_REQUEST,
                            msg_prefix=rsp.content.decode('utf-8'))

    def test_staff_change_providers(self):
        # Staff can change multiple providers
        self.user.is_staff = True
        self.user.save()
        provider1 = ProviderFactory()
        provider2 = ProviderFactory()
        # Tweak some data
        provider1.name_en = 'Jim-Bob'
        provider1.name_ar = 'Ahmed-Bob'
        provider1.name_fr = 'Pierre-Bob'
        provider2.number_of_monthly_beneficiaries = 1024
        provider2.type = ProviderTypeFactory()
        book = get_export_workbook([provider1, provider2])
        rsp = self.import_book(book)
        self.assertEqual(OK, rsp.status_code, msg=rsp.content.decode('utf-8'))
        new_provider1 = Provider.objects.get(id=provider1.id)
        self.assertEqual(provider1.name_en, new_provider1.name_en)
        self.assertEqual(provider1.name_ar, new_provider1.name_ar)
        self.assertEqual(provider1.name_fr, new_provider1.name_fr)
        new_provider2 = Provider.objects.get(id=provider2.id)
        self.assertEqual(provider2.number_of_monthly_beneficiaries,
                         new_provider2.number_of_monthly_beneficiaries)

    def test_provider_add_service(self):
        # A provider can create a new service for themselves
        provider = ProviderFactory(user=self.user)
        type = ServiceTypeFactory()
        area = ServiceAreaFactory()
        service = ServiceFactory.build(provider=provider, type=type, area_of_service=area,
                                       tuesday_open=time(6, 59),
                                       tuesday_close=time(21, 2))
        self.assertIsNotNone(service.location)
        criterion = SelectionCriterionFactory.build(
            service=service
        )
        book = get_export_workbook([provider], [service], [criterion])
        rsp = self.import_book(book)
        self.assertEqual(OK, rsp.status_code, msg=rsp.content.decode('utf-8'))
        new_service = Service.objects.get(name_en=service.name_en)
        self.assertEqual(new_service.name_en, service.name_en)
        self.assertTrue(SelectionCriterion.objects.filter(service=new_service,
                                                          text_en=criterion.text_en
                                                          ).exists())
        self.assertIsNotNone(new_service.location)
        self.assertEqual(service.location, new_service.location)
        self.assertEqual(service.tuesday_open, new_service.tuesday_open)
        self.assertEqual(service.tuesday_close, new_service.tuesday_close)

    def test_provider_add_bad_service(self):
        provider = ProviderFactory(user=self.user)
        type = ServiceTypeFactory()
        area = ServiceAreaFactory()
        service = ServiceFactory.build(provider=provider, type=type, area_of_service=area,
                                       name_en=VERY_LONG_STRING,
                                       tuesday_open=time(6, 59),
                                       tuesday_close=time(21, 2))
        self.assertIsNotNone(service.location)
        criterion = SelectionCriterionFactory.build(
            service=service
        )
        book = get_export_workbook([provider], [service], [criterion])
        rsp = self.import_book(book)
        self.assertEqual(BAD_REQUEST, rsp.status_code, msg=rsp.content.decode('utf-8'))

    def test_provider_add_anothers_service(self):
        # A provider can't add a service to another provider
        provider = ProviderFactory()
        type = ServiceTypeFactory()
        area = ServiceAreaFactory()
        service = ServiceFactory.build(provider=provider, type=type, area_of_service=area)
        book = get_export_workbook([provider], [service])
        rsp = self.import_book(book)
        self.assertEqual(BAD_REQUEST, rsp.status_code, msg=rsp.content.decode('utf-8'))
        self.assertContains(rsp, "%d is not a provider this user may import" % provider.id,
                            status_code=BAD_REQUEST)
        self.assertContains(rsp, "Non-staff users may not create services for other providers",
                            status_code=BAD_REQUEST)

    def test_provider_change_service(self):
        # A provider can change their existing service
        provider = ProviderFactory(user=self.user)
        type = ServiceTypeFactory()
        area = ServiceAreaFactory()
        service = ServiceFactory(provider=provider, type=type, area_of_service=area)
        service.name_en = 'Radiator Repair'
        service.name_fr = 'Le Marseilles'
        book = get_export_workbook([provider], [service])
        rsp = self.import_book(book)
        self.assertEqual(OK, rsp.status_code, msg=rsp.content.decode('utf-8'))
        new_service = Service.objects.get(id=service.id)
        self.assertEqual(service.name_en, new_service.name_en)
        self.assertEqual(service.name_fr, new_service.name_fr)

    def test_provider_change_nonexistent_service(self):
        provider = ProviderFactory(user=self.user)
        type = ServiceTypeFactory()
        area = ServiceAreaFactory()
        service = ServiceFactory(provider=provider, type=type, area_of_service=area)
        service.name_en = 'Radiator Repair'
        service.name_fr = 'Le Marseilles'
        book = get_export_workbook([provider], [service])
        service_id = service.id
        service.delete()
        rsp = self.import_book(book)
        self.assertContains(rsp, "%d is not a service this user may import" % service_id,
                            status_code=BAD_REQUEST)

    def test_provider_change_anothers_service(self):
        # A provider cannot change another provider's existing service
        provider = ProviderFactory()
        type = ServiceTypeFactory()
        area = ServiceAreaFactory()
        service = ServiceFactory(provider=provider, type=type, area_of_service=area)
        service.name_en = 'Radiator Repair'
        service.name_fr = 'Le Marseilles'
        book = get_export_workbook([provider], [service])
        rsp = self.import_book(book)
        # self.fail(rsp.content.decode('utf-8'))
        self.assertEqual(BAD_REQUEST, rsp.status_code, msg=rsp.content.decode('utf-8'))
        self.assertContains(rsp, "%d is not a provider this user may import" % provider.id,
                            status_code=BAD_REQUEST)
        self.assertContains(rsp, "%d is not a service this user may import" % service.id,
                            status_code=BAD_REQUEST)

    def test_staff_add_services(self):
        # Staff can add services to any provider
        self.user.is_staff = True
        self.user.save()
        provider = ProviderFactory()
        type = ServiceTypeFactory()
        area = ServiceAreaFactory()
        service = ServiceFactory.build(provider=provider, type=type, area_of_service=area)
        book = get_export_workbook([provider], [service])
        rsp = self.import_book(book)
        self.assertEqual(OK, rsp.status_code, msg=rsp.content.decode('utf-8'))
        new_service = Service.objects.get(name_en=service.name_en)
        self.assertEqual(new_service.name_en, service.name_en)

    def test_staff_change_services(self):
        # Staff can change anyone's service
        self.user.is_staff = True
        self.user.save()
        provider = ProviderFactory()
        type = ServiceTypeFactory()
        area = ServiceAreaFactory()
        service = ServiceFactory(provider=provider, type=type, area_of_service=area)
        service.name_en = 'Radiator Repair'
        service.name_fr = 'Le Marseilles'
        book = get_export_workbook([provider], [service])
        rsp = self.import_book(book)
        self.assertEqual(OK, rsp.status_code, msg=rsp.content.decode('utf-8'))
        new_service = Service.objects.get(id=service.id)
        self.assertEqual(service.name_en, new_service.name_en)
        self.assertEqual(service.name_fr, new_service.name_fr)

    def test_provider_add_criteria(self):
        provider = ProviderFactory(user=self.user)
        service = ServiceFactory(provider=provider, status=Service.STATUS_CURRENT)
        criterion1 = SelectionCriterionFactory(service=service)
        criterion2 = SelectionCriterionFactory.build(service=service, text_en="New Criterion!")
        book = get_export_workbook([provider], None, [criterion1, criterion2])
        rsp = self.import_book(book)
        self.assertEqual(OK, rsp.status_code, msg=rsp.content.decode('utf-8'))
        # Existing one still there
        self.assertTrue(SelectionCriterion.objects.filter(
            service=service,
            text_en=criterion1.text_en,
            id=criterion1.id
        ).exists())
        # New one added
        self.assertTrue(SelectionCriterion.objects.filter(
            service=service,
            text_en=criterion2.text_en
        ).exists())

    def test_provider_remove_criteria(self):
        provider = ProviderFactory(user=self.user)
        service = ServiceFactory(provider=provider, status=Service.STATUS_CURRENT)
        criterion1 = SelectionCriterionFactory(service=service)
        criterion2 = SelectionCriterionFactory(service=service)
        book = get_export_workbook([provider], None, [criterion1, criterion2],
                                   cell_overwrite_ok=True)

        # Blank out the 2nd one's data to indicate it should be deleted
        blank_out_row_for_testing(book, sheet_num=2, row_num=2)

        rsp = self.import_book(book)
        self.assertEqual(OK, rsp.status_code, msg=rsp.content.decode('utf-8'))
        # 1st one still there
        self.assertTrue(SelectionCriterion.objects.filter(
            service=service,
            text_en=criterion1.text_en,
            id=criterion1.id
        ).exists())
        # 2nd one removed
        self.assertFalse(SelectionCriterion.objects.filter(id=criterion2.id).exists())

    def test_provider_change_criteria(self):
        provider = ProviderFactory(user=self.user)
        service = ServiceFactory(provider=provider, status=Service.STATUS_CURRENT)
        criterion1 = SelectionCriterionFactory(service=service)
        criterion2 = SelectionCriterionFactory(service=service)
        # Change the 2nd one's text before exporting
        criterion2.text_en = criterion2.text_ar = criterion2.text_fr = 'Oh dear me'
        book = get_export_workbook([provider], None, [criterion1, criterion2])
        rsp = self.import_book(book)
        self.assertEqual(OK, rsp.status_code, msg=rsp.content.decode('utf-8'))
        # 1st one still there
        self.assertTrue(SelectionCriterion.objects.filter(
            service=service,
            text_en=criterion1.text_en,
            id=criterion1.id
        ).exists())
        # 2nd one changed
        crit2 = SelectionCriterion.objects.get(id=criterion2.id)
        self.assertEqual(crit2.text_en, criterion2.text_en)
        self.assertEqual(crit2.text_ar, criterion2.text_ar)
        self.assertEqual(crit2.text_fr, criterion2.text_fr)

    def test_provider_change_nonexistent_criterion(self):
        provider = ProviderFactory(user=self.user)
        service = ServiceFactory(provider=provider, status=Service.STATUS_CURRENT)
        criterion1 = SelectionCriterionFactory(service=service)
        book = get_export_workbook([provider], None, [criterion1])
        crit_id = criterion1.id
        criterion1.delete()
        rsp = self.import_book(book)
        self.assertContains(rsp, "Row 2: id: No selection criterion with id = %s" % crit_id,
                            status_code=BAD_REQUEST,
                            msg_prefix=rsp.content.decode('utf-8'))

    def test_provider_bad_criterion_id(self):
        provider = ProviderFactory(user=self.user)
        service = ServiceFactory(provider=provider, status=Service.STATUS_CURRENT)
        criterion1 = SelectionCriterionFactory.build(service=service)
        criterion1.id = 'abc'
        book = get_export_workbook([provider], None, [criterion1])
        rsp = self.import_book(book)
        self.assertContains(rsp, "Row 2: id: %s is not a valid ID" % criterion1.id,
                            status_code=BAD_REQUEST,
                            msg_prefix=rsp.content.decode('utf-8'))

    def test_provider_bad_criteria(self):
        provider = ProviderFactory(user=self.user)
        service = ServiceFactory(provider=provider, status=Service.STATUS_CURRENT)
        criterion1 = SelectionCriterionFactory(service=service)
        criterion2 = SelectionCriterionFactory(service=service)
        # Change the 2nd one's text before exporting
        criterion2.text_en = criterion2.text_ar = criterion2.text_fr = ''
        book = get_export_workbook([provider], None, [criterion1, criterion2])
        rsp = self.import_book(book)
        self.assertContains(rsp, "Selection criterion must have text in at least one language",
                            status_code=BAD_REQUEST,
                            msg_prefix=rsp.content.decode('utf-8'))

    def test_provider_add_criterion_bad_service(self):
        provider = ProviderFactory(user=self.user)
        criterion1 = SelectionCriterionFactory.build()
        service = criterion1.service
        book = get_export_workbook([provider], None, [criterion1])
        rsp = self.import_book(book)
        self.assertContains(rsp,
                            "Row 2: service__id: Selection criterion refers to service with ID "
                            "or name '%s' that is not in the 2nd sheet" % service.name_en,
                            status_code=BAD_REQUEST,
                            msg_prefix=rsp.content.decode('utf-8'))

    def test_provider_delete_service(self):
        # A provider can delete their existing service
        # by blanking out all the fields except id
        provider = ProviderFactory(user=self.user)
        type = ServiceTypeFactory()
        area = ServiceAreaFactory()
        service = ServiceFactory(provider=provider, type=type, area_of_service=area)
        self.assertTrue(Service.objects.filter(id=service.id).exists())
        book = get_export_workbook([provider], [service], cell_overwrite_ok=True)

        # Now blank out everything about the service except its 'id'
        blank_out_row_for_testing(book, sheet_num=1, row_num=1)

        rsp = self.import_book(book)
        self.assertEqual(OK, rsp.status_code, msg=rsp.content.decode('utf-8'))
        self.assertFalse(Service.objects.filter(id=service.id).exists())

    def test_provider_delete_nonexistent_service(self):
        provider = ProviderFactory(user=self.user)
        type = ServiceTypeFactory()
        area = ServiceAreaFactory()
        service = ServiceFactory(provider=provider, type=type, area_of_service=area)
        self.assertTrue(Service.objects.filter(id=service.id).exists())
        book = get_export_workbook([provider], [service], cell_overwrite_ok=True)
        service_id = service.id
        service.delete()

        # Now blank out everything about the service except its 'id'
        blank_out_row_for_testing(book, sheet_num=1, row_num=1)

        rsp = self.import_book(book)
        self.assertContains(rsp,
                            "Row 2: service: %d is not a service this user may delete" % service_id,
                            status_code=BAD_REQUEST,
                            msg_prefix=rsp.content.decode('utf-8'))

    def test_provider_delete_anothers_service(self):
        # A provider cannot delete someone else's service
        provider = ProviderFactory(user=self.user)
        type = ServiceTypeFactory()
        area = ServiceAreaFactory()
        service = ServiceFactory(type=type, area_of_service=area)
        self.assertTrue(Service.objects.filter(id=service.id).exists())
        book = get_export_workbook([provider], [service], cell_overwrite_ok=True)

        # Now blank out everything about the service except its 'id'
        blank_out_row_for_testing(book, sheet_num=1, row_num=1)

        rsp = self.import_book(book)
        self.assertContains(rsp, "%d is not a service this user may delete" % service.id,
                            status_code=BAD_REQUEST,
                            msg_prefix=rsp.content.decode('utf-8'))

    def test_staff_delete_service(self):
        # A staffer can delete someone else's service
        self.user.is_staff = True
        self.user.save()
        provider = ProviderFactory(user=self.user)
        type = ServiceTypeFactory()
        area = ServiceAreaFactory()
        service = ServiceFactory(type=type, area_of_service=area)
        self.assertTrue(Service.objects.filter(id=service.id).exists())
        book = get_export_workbook([provider], [service], cell_overwrite_ok=True)

        # Now blank out everything about the service except its 'id'
        blank_out_row_for_testing(book, sheet_num=1, row_num=1)

        rsp = self.import_book(book)
        self.assertEqual(OK, rsp.status_code, msg=rsp.content.decode('utf-8'))
        self.assertFalse(Service.objects.filter(id=service.id).exists())

    def test_staff_delete_nonexistent_service(self):
        self.user.is_staff = True
        self.user.save()
        provider = ProviderFactory(user=self.user)
        type = ServiceTypeFactory()
        area = ServiceAreaFactory()
        service = ServiceFactory(type=type, area_of_service=area)
        self.assertTrue(Service.objects.filter(id=service.id).exists())
        book = get_export_workbook([provider], [service], cell_overwrite_ok=True)
        service_id = service.id
        service.delete()

        # Now blank out everything about the service except its 'id'
        blank_out_row_for_testing(book, sheet_num=1, row_num=1)

        rsp = self.import_book(book)
        self.assertContains(rsp,
                            "No service with id=%d" % service_id,
                            status_code=BAD_REQUEST,
                            msg_prefix=rsp.content.decode('utf-8'))

    def test_provider_delete_provider(self):
        # A provider cannot delete themselves
        provider = ProviderFactory(user=self.user)
        book = get_export_workbook([provider], cell_overwrite_ok=True)
        blank_out_row_for_testing(book, sheet_num=0, row_num=1)
        rsp = self.import_book(book)
        self.assertContains(rsp, "Only staff may delete providers",
                            status_code=BAD_REQUEST,
                            msg_prefix=rsp.content.decode('utf-8'))

    def test_provider_delete_another_provider(self):
        # A provider cannot delete others
        provider = ProviderFactory()
        book = get_export_workbook([provider], cell_overwrite_ok=True)
        blank_out_row_for_testing(book, sheet_num=0, row_num=1)
        rsp = self.import_book(book)
        self.assertContains(rsp,
                            "provider: %d is not a provider this user may delete" % provider.id,
                            status_code=BAD_REQUEST,
                            msg_prefix=rsp.content.decode('utf-8'))

    def test_staff_delete_provider(self):
        # Staff may delete providers
        self.user.is_staff = True
        self.user.save()
        provider = ProviderFactory()
        book = get_export_workbook([provider], cell_overwrite_ok=True)
        blank_out_row_for_testing(book, sheet_num=0, row_num=1)
        rsp = self.import_book(book)
        self.assertEqual(OK, rsp.status_code, msg=rsp.content.decode('utf-8'))
        self.assertFalse(Provider.objects.filter(id=provider.id).exists())

    def test_provider_change_password(self):
        # Providers can change their password
        provider = ProviderFactory(user=self.user)
        book = get_export_workbook([provider], cell_overwrite_ok=True)
        password_column = PROVIDER_HEADINGS.index('password')
        set_cell_value(book, 0, 1, password_column, 'new_password')
        rsp = self.import_book(book)
        self.assertEqual(OK, rsp.status_code, msg=rsp.content.decode('utf-8'))
        user = authenticate(email=provider.user.email,
                            password='new_password')
        self.assertEqual(user, self.user)

    def test_provider_change_anothers_password(self):
        # Providers cannot change another provider's password
        provider = ProviderFactory()
        book = get_export_workbook([provider], cell_overwrite_ok=True)
        password_column = PROVIDER_HEADINGS.index('password')
        set_cell_value(book, 0, 1, password_column, 'new_password')
        rsp = self.import_book(book)
        self.assertEqual(BAD_REQUEST, rsp.status_code, msg=rsp.content.decode('utf-8'))
        user = authenticate(email=provider.user.email,
                            password='new_password')
        self.assertIsNone(user)

    def test_staff_change_provider_password(self):
        # Staff can change anyone's password
        self.user.is_staff = True
        self.user.save()
        provider = ProviderFactory()
        book = get_export_workbook([provider], cell_overwrite_ok=True)
        password_column = PROVIDER_HEADINGS.index('password')
        set_cell_value(book, 0, 1, password_column, 'new_password')
        rsp = self.import_book(book)
        self.assertEqual(OK, rsp.status_code, msg=rsp.content.decode('utf-8'))
        user = authenticate(email=provider.user.email,
                            password='new_password')
        self.assertEqual(user, provider.user)
