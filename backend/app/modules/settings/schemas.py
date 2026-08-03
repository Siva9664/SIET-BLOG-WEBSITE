from pydantic import BaseModel, ConfigDict


class SettingsResponse(BaseModel):
    site_name: str
    credit_line: str
    accent_color: str
    newsletter_enabled: bool
    featured_domains: str

    model_config = ConfigDict(from_attributes=True)


class SettingsUpdate(BaseModel):
    site_name: str | None = None
    credit_line: str | None = None
    accent_color: str | None = None
    newsletter_enabled: bool | None = None
    featured_domains: str | None = None
