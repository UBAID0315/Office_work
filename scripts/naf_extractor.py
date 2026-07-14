import json
import os
from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient

def identify_naf(pdf_path, endpoint, key):
    client = DocumentIntelligenceClient(
        endpoint=endpoint,
        credential=AzureKeyCredential(key),
    )

    with open(pdf_path, "rb") as f:
        poller = client.begin_classify_document(
            classifier_id="naf_identifier",
            body=f,
        )

    result = poller.result()

    if result.documents:
        doc = result.documents[0]
        return doc.doc_type, doc.confidence
    return None, 0.0

#==================
# Helper Functions
#==================

def confidence(node):
    return node.get("confidence") if isinstance(node, dict) else None

def val(node):
    if node is None:
        return {"value": None, "confidence": None}

    if not isinstance(node, dict):
        return {"value": node, "confidence": None}

    value = next(
        (
            clean(node[k])
            for k in (
                "valueString",
                "valueNumber",
                "valueDate",
                "valueSignature",
                "content",
            )
            if node.get(k) is not None
        ),
        None,
    )

    return {
        "value": value,
        "confidence": node.get("confidence"),
    }

def clean(text):
    if not isinstance(text, str):
        return text
    
    import re
    # Remove leading section-number artifacts only when followed by a full sentence
    # i.e. uppercase word + space + more content: "17 We hereby certify..."
    # Safe against: "20 years", "60 Year.", "0335 - 1342432", "10,000,000"
    text = re.sub(r'^\d+[\s\.]+(?=[A-Z][a-z]+\s)', '', text)
    
    parts = text.replace("\n", " ").split()
    joined = " ".join(parts).strip()

    result = []
    for i, ch in enumerate(joined):
        if (
            ch == " "
            and i > 0
            and joined[i - 1] == ","
            and i + 1 < len(joined)
            and joined[i + 1].isdigit()
        ):
            continue
        result.append(ch)
    return "".join(result)

def first(array_node):
    if not isinstance(array_node, dict):
        return {}
    items = array_node.get("valueArray", [])
    if not items:
        return {}
    return items[0].get("valueObject", {})

def all_objects(array_node):
    if not isinstance(array_node, dict):
        return []
    return [item.get("valueObject", {}) for item in array_node.get("valueArray", [])]

def obj(node, key):
    return val(node.get(key)) if isinstance(node, dict) else {
        "value": None,
        "confidence": None,
    }

CHECKBOX_FIELDS = {
    "state_of_health": {
        "soh_excellent": "Excellent",
        "soh_vgood": "Very Good",
        "soh_good": "Good",
        "soh_moderate": "Moderate",
        "soh_poor": "Poor",
    },
    "smoker": {
        "somker_yes": "Yes",
        "smoker_no": "No",
    },
    "family_expansion": {
        "expansion_yes": "Yes",
        "expansion_no": "No",
    },
    "pension_scheme": {
        "scheme_yes": "Yes",
        "scheme_no": "No",
    },
    "investment_horizon": {
        "invest_short": "Short term (<1 yr)",
        "invest_medium": "Medium (1-5 yrs)",
        "invest_medlong": "Medium-Long (5-10 yrs)",
        "invest_long": "Long term (>10 yrs)",
    },
    "investment_knowledge": {
        "little_kn": "Little knowledge",
        "some_kn": "Some knowledge",
        "both_kn": "Both knowledge & experienced",
    },
    "financial_position": {
        "very_secure": "Very secure",
        "somewhat_secure": "Somewhat secure",
        "not_sure": "Not sure",
        "likely_worse": "Likely worse",
    },
    "life_stage": {
        "ls_childhood": "Childhood",
        "ls_y_um": "Young unmarried",
        "ls_y_m": "Young married",
        "ls_y_m_c": "Young married w/ children",
        "ls_m_oc": "Married w/ older children",
        "post_family": "Post-family",
        "pre_retire": "Pre-retirement",
        "retirement": "Retirement",
    },
    "protection_needs": {
        "life_and_health": "Life & Health",
        "savings_and_investment": "Savings & Investment",
        "pension": "Pension",
    },
    "risk_appetite": {
        "app_low": "Low",
        "app_medium": "Medium",
        "app_high": "High",
    },
    "risks_explained": {
        "risks_yes": "Yes",
        "risks_no": "No",
    },
}

def checkbox(data, group):
    mapping = CHECKBOX_FIELDS[group]
    selected = None
    confidence = None

    for field, option in mapping.items():
        node = data.get(field)
        if (
            isinstance(node, dict)
            and node.get("valueSelectionMark") == "selected"
        ):
            selected = option
            confidence = node.get("confidence")
            break

    return {
        "selected": selected,
        "options": list(mapping.values()),
        "confidence": confidence,
    }

def build(data):
    basic = first(data.get("Basic_Information", {}))
    employment = first(data.get("Employment_details", {}))
    financial = first(data.get("Financial_Details", {}))
    pension = first(data.get("Pension_details", {}))
    saving = first(data.get("Future_saving_needs", {}))
    priorities = first(data.get("Financial_priorities", {}))
    needs = first(data.get("Family_takaful", {}))

    family = all_objects(data.get("Family_Details", {}))
    plans = all_objects(data.get("Family_plans", {}))

    # Resolve ftn_name and basic name with mutual fallback
    ftn_name_val  = val(data.get("ftn_name"))
    basic_name_val = obj(basic, "name")

    # If ftn_name is missing/null, copy value from basic name
    if not ftn_name_val.get("value"):
        ftn_name_val = {
            "value": basic_name_val.get("value"),
            "confidence": basic_name_val.get("confidence"),
        }

    # If basic name is missing/null, copy value from ftn_name
    if not basic_name_val.get("value"):
        basic_name_val = {
            "value": ftn_name_val.get("value"),
            "confidence": ftn_name_val.get("confidence"),
        }

    form = {
        "form_title": "Adamjee Life Assurance Co. Ltd - Window Takaful Operations - Needs Analysis Form",
        "family_takaful_need_analysis_of": ftn_name_val,
        "section_1_basic_information": {
            "name": basic_name_val,
            "address": obj(basic, "address"),
            "telephone": obj(basic, "telephone"),
            "email": obj(basic, "email"),
            "date_of_birth": obj(basic, "date_of_birth"),
            "marital_status": obj(basic, "martial_status"),
            "state_of_health": checkbox(data, "state_of_health"),
            "smoker": checkbox(data, "smoker"),
        },
        "section_2_family_details": {
            "number_of_dependents": val(data.get("No_of_dependents")),
            "dependents": [
                {
                    "name": obj(member, "Name"),
                    "relationship": obj(member, "Relationship"),
                    "age": obj(member, "Age"),
                    "state_of_health": obj(member, "State_of_health"),
                    "occupation": obj(member, "Occupation"),
                }
                for member in family
            ],
            "scope_for_family_expansion": checkbox(data, "family_expansion"),
        },
        "section_3_employment_details": {
            "occupation": obj(employment, "Occupation"),
            "length_of_service": obj(employment, "Length_of_service"),
            "annual_income": obj(employment, "Annual_income"),
            "normal_retirement_age": obj(employment, "Retirement_age"),
            "covered_under_pension_scheme": checkbox(data, "pension_scheme"),
        },
        "section_4_financial_details": {
            "value_of_savings_and_assets": obj(financial, "Value_of_assets"),
            "liabilities_outstanding_loans": obj(financial, "Details_of_liabilities"),
            "expected_inheritance": obj(financial, "Expected_inheritance"),
        },
        "section_5_pension_details": {
            "employers_scheme_insurance_takaful": obj(pension, "Type_of_pension"),
            "personal_premium_contribution": obj(pension, "Premium/Contribution"),
            "retirement_age": obj(pension, "Retirement_age"),
            "anticipated_value": obj(pension, "Anticipated_value"),
        },
        "section_6_future_saving_needs": {
            "for_education_of_children": obj(saving, "Education_for_children"),
            "for_wedding": obj(saving, "For_wedding"),
            "for_house_purchase": obj(saving, "For_house_purchase"),
            "others": obj(saving, "Others"),
        },
        "section_7_existing_plans": [
            {
                "company_takaful_operator": obj(plan, "Company/Takaful_operator"),
                "policy_certificate_no": obj(plan, "Policy_no/certificate_no"),
                "sum_assured_covered": obj(plan, "Sum_assured/sum_covered"),
                "premium_contribution": obj(plan, "Premium/Contribution"),
                "start_date": obj(plan, "Start_date"),
                "maturity_date": obj(plan, "Maturity_date"),
                "purpose": obj(plan, "Purpose"),
            }
            for plan in plans
        ],
        "section_8_financial_priorities": {
            "financial_security_event_of_death": obj(priorities, "fs_event_of_death"),
            "financial_security_critical_illness": obj(priorities, "fs_event_critical_illness"),
            "providing_retirement_income": obj(priorities, "retirement_income"),
            "planning_childrens_education": obj(priorities, "child's_education"),
            "planning_childrens_wedding": obj(priorities, "child's_wedding"),
            "building_capital_regular_saving": obj(priorities, "capital_regular_saving"),
            "investing_capital_better_return": obj(priorities, "capital_for_better_return"),
            "investment_horizon": checkbox(data, "investment_horizon"),
            "investment_knowledge_level": checkbox(data, "investment_knowledge"),
            "current_financial_position": checkbox(data, "financial_position"),
        },
        "section_9_identified_takaful_needs": {
            "life_insurance_death_maturity": obj(needs, "Life_insurance"),
            "desirable_sum_covered": obj(needs, "Desireable_sum"),
            "health_family_takaful": obj(needs, "Takaful"),
            "desirable_limit_coverage_per_annum": obj(needs, "Dl_per_annum"),
            "saving_investment_planning": obj(needs, "saving_planning"),
            "desirable_returns_per_annum": obj(needs, "Dr_per_annum"),
            "pension_planning": obj(needs, "Pension_planning"),
            "desirable_pension_per_annum": obj(needs, "Desireable_pension"),
        },
        "section_10_additional_information": obj(needs, "Any_add_info"),
        "section_11_recommendation": {
            "life_stage": checkbox(data, "life_stage"),
            "protection_needs": checkbox(data, "protection_needs"),
            "appetite_for_risk": checkbox(data, "risk_appetite"),
            "plan_recommended": obj(needs, "Plan_recommended"),
            "commitment_current_future_years": obj(needs, "Commitment"),
            "all_risks_charges_explained": checkbox(data, "risks_explained"),
            "why_plan_most_suited": obj(needs, "Why_best_plan"),
        },
        "sales_officer_certification": {
            "statement": val(data.get("s_o_certificate")),
            "date": val(data.get("certificate_date")),
            "name": val(data.get("soc_name")),
            "signature": val(data.get("certificate_sign")),
        },
        "prospect_acknowledgement": {
            "statement": val(data.get("prospect_ack")),
            "acknowledgements": {
                "a": val(data.get("option_a")),
                "b": val(data.get("option_b")),
                "c": val(data.get("option_c")),
                "d": val(data.get("option_d")),
                "e": val(data.get("option_e")),
                "f": val(data.get("option_f")),
                "g": val(data.get("option_g")),
            },
            "date": val(data.get("prospect_date")),
            "signature": val(data.get("prospect_sign")),
        },
    }
    return form

def merge_fields(base, extra):
    result = dict(base)
    for key, value in extra.items():
        if key not in result or is_empty(result[key]):
            result[key] = value
    return result

def is_empty(node):
    if node is None:
        return True
    if isinstance(node, dict):
        return val(node) in (None, "")
    return node in (None, "")

def extract_with_azure(pdf_path, endpoint, key, model_ids):
    client = DocumentIntelligenceClient(
        endpoint=endpoint, credential=AzureKeyCredential(key)
    )

    merged = {}
    for model_id in model_ids:
        with open(pdf_path, "rb") as f:
            poller = client.begin_analyze_document(model_id, body=f)
        result = poller.result()

        if not result.documents:
            continue

        fields = result.documents[0].fields
        if hasattr(fields, "as_dict"):
            fields = fields.as_dict()
        else:
            fields = json.loads(json.dumps(fields, default=lambda o: dict(o)))

        merged = merge_fields(merged, fields)

    client.close()

    if not merged:
        raise Exception("Neither model returned fields. Check the model ids and form.")

    return merged

def extract_naf_fields(pdf_path, endpoint, key, model_ids):

    try:
        # This function is calling classfier to identify the document type and confidence
        verified_naf = identify_naf(pdf_path, endpoint, key)
        doc_type, confidence = verified_naf
        
        if doc_type != "naf_detected" and confidence < 0.85:
            raise ValueError(f"Facing difficulty in identifying NAF document (!Use clear image). Extraction aborted.")

        data = extract_with_azure(pdf_path, endpoint, key, model_ids)
        result = build(data)
        return result

    except Exception as e:
        raise ValueError(f"Error identifying NAF document: {e}")
