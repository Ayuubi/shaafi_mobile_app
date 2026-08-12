# apps/shaafi_mobile_app/shaafi_mobile_app/utils/erpnext_utils.py

import frappe


def get_mobile_app_defaults():
    """Fetches default company, cost center, and mode of payment from Mobile App Settings."""

    settings = frappe.get_single("Mobile App Settings")

    return {
        "company": settings.default_company,
        "cost_center": settings.default_cost_center,
        "mode_of_payment": settings.default_mode_of_payment,
        "source_order" : settings.default_source_order,
    }
