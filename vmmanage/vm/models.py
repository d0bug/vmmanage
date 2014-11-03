from django.db import models

# Create your models here.

#class Vminfo(models.Model):
#    id = models.IntegerField(primary_key=True)
#    vm_name = models.CharField(max_length=50)
#    vm_ip = models.CharField(max_length=20)
#    vm_owner = models.CharField(max_length=20)
#    host = models.CharField(max_length=100)
#    last_op = models.CharField(max_length=20)
#    stime = models.DateTimeField()
#    time = models.DateTimeField()
#    class Meta:
#        managed = False
#        db_table = 'vminfo'

class VpnUser(models.Model):
    '''VPN user information'''
    username = models.CharField(primary_key=True, max_length=20)
    password = models.CharField(max_length=128, blank=True)
    email = models.CharField(max_length=128, blank=True)
    active = models.IntegerField()
    alias = models.CharField(max_length=20, blank=True)
    department = models.CharField(max_length=20)
    created_at = models.DateTimeField()
    class Meta:
        managed = False
        db_table = 'vpn_user'

class VmInfo(models.Model):
    '''QA env information'''
    id = models.BigIntegerField(primary_key=True)
    hostname = models.CharField(max_length=40, blank=True)
    ip = models.CharField(unique=True, max_length=20)
    owner = models.CharField(max_length=20)
    result = models.IntegerField(blank=True, null=True)
    updatetime = models.DateTimeField()
    role = models.CharField(max_length=10, blank=True)
    class Meta:
        managed = False
        db_table = 'vm_info'

class Tpl(models.Model):
    '''Template type'''
    tplname = models.CharField(max_length=50)
    vmconfig = models.CharField(max_length=100)
    hostip = models.CharField(max_length=20)
    vmip = models.CharField(max_length=20)
    chinesename = models.CharField(max_length=50)

class Info(models.Model):
    '''VM information'''
    vmname = models.CharField(max_length=50, blank=True)
    vmip = models.CharField(max_length=20, blank=True)
    vmowner = models.CharField(max_length=20)
    hostip = models.CharField(max_length=20, blank=True)
    vmstatus = models.CharField(max_length=10, blank=True)
    tpl = models.CharField(max_length=50)
    type = models.CharField(max_length=10)
    submittime = models.DateTimeField(auto_now=True)
    starttime = models.DateTimeField(blank=True, null=True)
    exptime = models.DateTimeField(blank=True, null=True)
    opexam = models.BooleanField(default=0)
    passexam = models.BooleanField(default=0)
    used = models.BooleanField(default=0)
    failed = models.BooleanField(default=0)

