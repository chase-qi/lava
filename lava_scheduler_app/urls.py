from django.conf.urls.defaults import url, patterns


urlpatterns = patterns(
    'lava_scheduler_app.views',
    url(r'^$',
        'index',
        name='lava.scheduler'),
    url(r'^reports$',
        'reports',
        name='lava.scheduler.reports'),
    url(r'^reports/failures$',
        'failure_report',
        name='lava.scheduler.failure_report'),
    url(r'^reports/failures_json$',
        'failed_jobs_json',
        name='lava.scheduler.failed_jobs_json'),
    url(r'^active_jobs_json$',
        'index_active_jobs_json',
        name='lava.scheduler.active_jobs_json'),
    url(r'^devices_json$',
        'index_devices_json',
        name='lava.scheduler.index_devices_json'),
    url(r'^worker_json$',
        'index_worker_json',
        name='lava.scheduler.index_worker_json'),
    url(r'^edit_worker_desc',
        'edit_worker_desc',
        name='lava.scheduler.edit_worker_desc'),
    url(r'^alljobs$',
        'job_list',
        name='lava.scheduler.job.list'),
    url(r'^jobsubmit$',
        'job_submit',
        name='lava.scheduler.job.submit'),
    url(r'^alljobs_json$',
        'alljobs_json',
        name='lava.scheduler.job.list_json'),
    url(r'^device_type/(?P<pk>[-_a-zA-Z0-9]+)$',
        'device_type_detail',
        name='lava.scheduler.device_type.detail'),
    url(r'^device_type_json$',
        'device_type_json',
        name='lava.scheduler.device_type.device_type_json'),
    url(r'^device_type/(?P<pk>[-_a-zA-Z0-9]+)/index_nodt_devices_json$',
        'index_nodt_devices_json',
        name='lava.scheduler.device_type.index_nodt_devices_json'),
    url(r'^alldevices$',
        'device_list',
        name='lava.scheduler.alldevices'),
    url(r'^device/(?P<pk>[-_a-zA-Z0-9]+)$',
        'device_detail',
        name='lava.scheduler.device.detail'),
    url(r'^worker/(?P<pk>[-_a-zA-Z0-9.]+)$',
        'worker_detail',
        name='lava.scheduler.worker.detail'),
    url(r'^worker/(?P<pk>[-_a-zA-Z0-9.]+)/worker_device_json$',
        'worker_device_json',
        name='lava.scheduler.worker.worker_device_json'),
    url(r'^device/(?P<pk>[-_a-zA-Z0-9]+)/recent_jobs_json$',
        'recent_jobs_json',
        name='lava.scheduler.device.recent_jobs_json'),
    url(r'^device/(?P<pk>[-_a-zA-Z0-9]+)/transition_json$',
        'transition_json',
        name='lava.scheduler.device.transition_json'),
    url(r'^edit-transition',
        'edit_transition',
        name='lava.scheduler.edit_transition'),
    url(r'^device/(?P<pk>[-_a-zA-Z0-9]+)/maintenance$',
        'device_maintenance_mode',
        name='lava.scheduler.device.maintenance'),
    url(r'^device/(?P<pk>[-_a-zA-Z0-9]+)/forcehealthcheck$',
        'device_force_health_check',
        name='lava.scheduler.device.forcehealthcheck'),
    url(r'^device/(?P<pk>[-_a-zA-Z0-9]+)/looping$',
        'device_looping_mode',
        name='lava.scheduler.device.looping'),
    url(r'^device/(?P<pk>[-_a-zA-Z0-9]+)/online$',
        'device_online',
        name='lava.scheduler.device.online'),
    url(r'^labhealth/$',
        'lab_health',
        name='lava.scheduler.labhealth'),
    url(r'^labhealth/health_json$',
        'lab_health_json',
        name='lava.scheduler.labhealth_json'),
    url(r'^labhealth/device/(?P<pk>[-_a-zA-Z0-9]+)$',
        'health_job_list',
        name='lava.scheduler.labhealth.detail'),
    url(r'^labhealth/device/(?P<pk>[-_a-zA-Z0-9]+)/job_json$',
        'health_jobs_json',
        name='lava.scheduler.labhealth.health_jobs_json'),
    url(r'^job/(?P<pk>[0-9]+|[0-9]+.[0-9]+)$',
        'job_detail',
        name='lava.scheduler.job.detail'),
    url(r'^job/(?P<pk>[0-9]+)/definition$',
        'job_definition',
        name='lava.scheduler.job.definition'),
    url(r'^job/(?P<pk>[0-9]+)/definition/plain$',
        'job_definition_plain',
        name='lava.scheduler.job.definition.plain'),
    url(r'^job/(?P<pk>[0-9]+)/multinode_definition$',
        'multinode_job_definition',
        name='lava.scheduler.job.multinode_definition'),
    url(r'^job/(?P<pk>[0-9]+)/multinode_definition/plain$',
        'multinode_job_definition_plain',
        name='lava.scheduler.job.multinode_definition.plain'),
    url(r'^job/(?P<pk>[0-9]+)/log_file$',
        'job_log_file',
        name='lava.scheduler.job.log_file'),
    url(r'^job/(?P<pk>[0-9]+)/log_file/plain$',
        'job_log_file_plain',
        name='lava.scheduler.job.log_file.plain'),
    url(r'^job/(?P<pk>[0-9]+)/cancel$',
        'job_cancel',
        name='lava.scheduler.job.cancel'),
    url(r'^job/(?P<pk>[0-9]+)/resubmit$',
        'job_resubmit',
        name='lava.scheduler.job.resubmit'),
    url(r'^job/(?P<pk>[0-9]+)/annotate_failure$',
        'job_annotate_failure',
        name='lava.scheduler.job.annotate_failure'),
    url(r'^job/(?P<pk>[0-9]+)/json$',
        'job_json',
        name='lava.scheduler.job.json'),
    url(r'^job/(?P<pk>[0-9]+)/output$',
        'job_output',
        name='lava.scheduler.job.output'),
    url(r'^job/(?P<pk>[0-9]+)/log_incremental$',
        'job_log_incremental',
        name='lava.scheduler.job.log_incremental'),
    url(r'^job/(?P<pk>[0-9]+)/full_log_incremental$',
        'job_full_log_incremental',
        name='lava.scheduler.job.full_log_incremental'),
    url(r'^get-remote-json',
        'get_remote_json',
        name='lava.scheduler.get_remote_json'),
    url(r'^myjobs$',
        'myjobs',
        name='lava.scheduler.myjobs'),
    url(r'^myjobs_json$',
        'myjobs_json',
        name='lava.scheduler.job.list_json'),
    url(r'^job/(?P<pk>[0-9]+)/priority$',
        'job_change_priority',
        name='lava.scheduler.job.priority'),
    url(r'^device/(?P<pk>[-_a-zA-Z0-9]+)/restrict$',
        'device_restrict_device',
        name='lava.scheduler.device.restrict_device'),
    url(r'^device/(?P<pk>[-_a-zA-Z0-9]+)/derestrict$',
        'device_derestrict_device',
        name='lava.scheduler.device.derestrict_device'),
    url(r'^device/(?P<pk>[-_a-zA-Z0-9]+)/description$',
        'device_edit_description',
        name='lava.scheduler.device.edit_description'),
    url(r'^transition/(?P<pk>[0-9]+)$',
        'transition_detail',
        name='lava.scheduler.transition_detail'),
    url(r'^device_type_jobs_json/(?P<pk>[-_a-zA-Z0-9]+)$',
        'device_type_jobs_json',
        name='lava.scheduler.device_type_jobs_json'),
    url(r'^alldevices/active$',
        'active_device_list',
        name='lava.scheduler.active_devices'),
    url(r'^scheduler/reports/device/(?P<pk>[-_a-zA-Z0-9]+)',
        'device_reports',
        name='lava.scheduler.device_report'),
    url(r'^scheduler/reports/device_type/(?P<pk>[-_a-zA-Z0-9]+)',
        'device_type_reports',
        name='lava.scheduler.device_type_report'),
    url(r'^mydevices$',
        'mydevice_list',
        name='lava.scheduler.mydevice_list'),
    url(r'^mydevices_json$',
        'mydevices_json',
        name='lava.scheduler.mydevices_json'),
)
