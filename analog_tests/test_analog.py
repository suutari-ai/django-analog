import pytest
from analog import define_log_model, LogEntryKind, BaseLogEntry
from analog.exceptions import UnknownLogKind
from analog_tests.models import LoggedModel, LoggedModelLogEntry
from django.db import models


class RandomModel(models.Model):
    pass


def qs_last(qs):  # Compatibility shim for old Djangos
    try:
        return qs.last()
    except AttributeError:
        return list(qs.all())[-1]



def test_model_sanity():
    RandomModelLogEntry = define_log_model(RandomModel)
    assert RandomModelLogEntry.__module__ == RandomModel.__module__
    assert RandomModelLogEntry._meta.get_field("target").rel.to is RandomModel
    try:
        rel = RandomModel.log_entries.related
        # TODO: Assert here too?
    except AttributeError:  # Django 1.9+
        rel = RandomModel.log_entries.rel
        assert rel.model is RandomModel
        assert rel.related_model is RandomModelLogEntry

    assert issubclass(RandomModelLogEntry, BaseLogEntry)
    assert isinstance(RandomModelLogEntry(), BaseLogEntry)


@pytest.mark.django_db
@pytest.mark.parametrize("kwarg", (False, True))
def test_add_log_entry(kwarg):
    lm = LoggedModel.objects.create()
    if kwarg:
        lm.add_log_entry(message="hello, world")
    else:
        lm.add_log_entry("hello, world")
    assert lm.log_entries.count() == 1
    log_entry = qs_last(lm.log_entries)
    assert isinstance(log_entry, LoggedModelLogEntry)
    assert isinstance(log_entry, BaseLogEntry)


@pytest.mark.django_db
def test_log_entry_kind():
    lm = LoggedModel.objects.create()
    lm.add_log_entry(message="edited", kind=LogEntryKind.EDIT)
    log_entry = qs_last(lm.log_entries)
    assert log_entry.get_kind_display() == "edit"


@pytest.mark.django_db
def test_log_mutation():
    lm = LoggedModel.objects.create()
    lm.add_log_entry(message="benign action", kind=LogEntryKind.EDIT)
    log_entry = qs_last(lm.log_entries)
    log_entry.message = "sneak"
    with pytest.raises(ValueError):
        log_entry.save()


@pytest.mark.django_db
def test_user_logging(admin_user):
    lm = LoggedModel.objects.create()
    lm.add_log_entry(message="audit", kind=LogEntryKind.AUDIT, user=admin_user)
    log_entry = qs_last(lm.log_entries)
    assert log_entry.user.is_superuser  # we put an admin in


@pytest.mark.django_db
def test_modify_before_save():
    lm = LoggedModel.objects.create()
    le = lm.add_log_entry(message="hi", save=False)
    le.message = "hey"
    le.save()
    le = qs_last(lm.log_entries)
    assert le.message == "hey"


@pytest.mark.django_db
def test_custom_kind():
    lm = LoggedModel.objects.create()
    le = lm.add_log_entry(message="custom", kind="custom_kind")
    assert le.kind == 3010
    assert le.get_kind_display() == "very custom"


@pytest.mark.django_db
def test_invalid_kinds():
    lm = LoggedModel.objects.create()

    with pytest.raises(UnknownLogKind):
        lm.add_log_entry(message="custom", kind="is0wdfjgwr")

    with pytest.raises(UnknownLogKind):
        lm.add_log_entry(message="custom", kind=43524)
