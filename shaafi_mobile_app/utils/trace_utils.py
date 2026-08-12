# apps/shaafi_mobile_app/shaafi_mobile_app/utils/trace_utils.py

import frappe


def log_mobile_api_failure(api, step, context=None, error=None, http_status_code=None):
    """Write one Error Log row per API failure with searchable context."""
    payload = {
        "api": api,
        "step": step,
        "http_status_code": http_status_code,
        "session_user": frappe.session.user,
        "context": {k: v for k, v in (context or {}).items() if v is not None},
    }
    if error:
        payload["error"] = str(error)

    message = frappe.as_json(payload, indent=2)
    if error and not isinstance(error, str):
        message += "\n\n" + frappe.get_traceback()

    frappe.log_error(title=f"Mobile App API | {api} | {step}", message=message)


def appointment_trace_context(PID=None, doctor_practitioner=None, appointment_date=None, **extra):
    """Build trace context for appointment APIs."""
    patient_mobile = None
    if PID and frappe.db.exists("Patient", PID):
        patient_mobile = frappe.db.get_value("Patient", PID, "mobile_no")

    return {
        "PID": PID,
        "patient_mobile": patient_mobile,
        "doctor_practitioner": doctor_practitioner,
        "appointment_date": appointment_date,
        **extra,
    }


def order_trace_context(sales_order_id=None, so_doc=None, mobile=None, **extra):
    """Build trace context for order APIs."""
    context = {
        "sales_order_id": sales_order_id,
        "mobile": mobile,
    }
    if so_doc:
        context.update({
            "patient": getattr(so_doc, "patient", None),
            "customer": getattr(so_doc, "customer", None),
            "contact_mobile": getattr(so_doc, "contact_mobile", None),
        })
    context.update(extra)
    return context


def patient_trace_context(mobile=None, patient_id=None, full_name=None, **extra):
    """Build trace context for patient APIs."""
    return {
        "mobile": mobile,
        "patient_id": patient_id,
        "full_name": full_name,
        **extra,
    }
