from tortoise.models import Model
from tortoise.fields import SmallIntField, IntField, BigIntField, FloatField, CharField, TextField, DatetimeField, BooleanField, JSONField
# from urllib.parse import quote, unquote

class BackupTask(Model):
    time = DatetimeField()
    local_dir = TextField()
    settings_alist = JSONField()
    status = CharField(max_length=35)
