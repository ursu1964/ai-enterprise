class EnterpriseKernelError(Exception):
    code = "enterprise_kernel_error"


class InvalidEnterpriseResource(EnterpriseKernelError):
    code = "invalid_enterprise_resource"


class EnterpriseResourceAlreadyExists(EnterpriseKernelError):
    code = "enterprise_resource_already_exists"


class EnterpriseResourceNotFound(EnterpriseKernelError):
    code = "enterprise_resource_not_found"


class EnterpriseScheduleAlreadyExists(EnterpriseKernelError):
    code = "enterprise_schedule_already_exists"


class EnterpriseScheduleNotFound(EnterpriseKernelError):
    code = "enterprise_schedule_not_found"


class InvalidEnterpriseSchedule(EnterpriseKernelError):
    code = "invalid_enterprise_schedule"
