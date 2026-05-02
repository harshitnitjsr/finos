import contextvars

# Global context variable to store the organization ID for the current request.
# Used by LangChain tools to access the tenant without passing it through tool schemas.
org_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("org_id")
