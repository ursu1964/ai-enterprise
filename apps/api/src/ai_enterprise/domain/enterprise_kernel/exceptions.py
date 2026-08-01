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


class EnterpriseModuleAlreadyExists(EnterpriseKernelError):
    code = "enterprise_module_already_exists"


class EnterpriseModuleNotFound(EnterpriseKernelError):
    code = "enterprise_module_not_found"


class OrganizationalThreadAlreadyExists(EnterpriseKernelError):
    code = "organizational_thread_already_exists"


class OrganizationalThreadNotFound(EnterpriseKernelError):
    code = "organizational_thread_not_found"


class InvalidEnterpriseModule(EnterpriseKernelError):
    code = "invalid_enterprise_module"


class InvalidOrganizationalThread(EnterpriseKernelError):
    code = "invalid_organizational_thread"


class InvalidOperatingMaturity(EnterpriseKernelError):
    code = "invalid_operating_maturity"


class OperatingMaturityAlreadyExists(EnterpriseKernelError):
    code = "operating_maturity_already_exists"
