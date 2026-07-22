 
============================================================
📂 UPLOAD YOUR NAF PDF FILE BELOW:
============================================================

     
     naf.pdf(application/pdf) - 2658389 bytes, last modified: n/a - 100% done
      // Copyright 2017 Google LLC
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

/**
 * @fileoverview Helpers for google.colab Python module.
 */
(function(scope) {
function span(text, styleAttributes = {}) {
  const element = document.createElement('span');
  element.textContent = text;
  for (const key of Object.keys(styleAttributes)) {
    element.style[key] = styleAttributes[key];
  }
  return element;
}

// Max number of bytes which will be uploaded at a time.
const MAX_PAYLOAD_SIZE = 100 * 1024;

function _uploadFiles(inputId, outputId) {
  const steps = uploadFilesStep(inputId, outputId);
  const outputElement = document.getElementById(outputId);
  // Cache steps on the outputElement to make it available for the next call
  // to uploadFilesContinue from Python.
  outputElement.steps = steps;

  return _uploadFilesContinue(outputId);
}

// This is roughly an async generator (not supported in the browser yet),
// where there are multiple asynchronous steps and the Python side is going
// to poll for completion of each step.
// This uses a Promise to block the python side on completion of each step,
// then passes the result of the previous step as the input to the next step.
function _uploadFilesContinue(outputId) {
  const outputElement = document.getElementById(outputId);
  const steps = outputElement.steps;

  const next = steps.next(outputElement.lastPromiseValue);
  return Promise.resolve(next.value.promise).then((value) => {
    // Cache the last promise value to make it available to the next
    // step of the generator.
    outputElement.lastPromiseValue = value;
    return next.value.response;
  });
}

/**
 * Generator function which is called between each async step of the upload
 * process.
 * @param {string} inputId Element ID of the input file picker element.
 * @param {string} outputId Element ID of the output display.
 * @return {!Iterable<!Object>} Iterable of next steps.
 */
function* uploadFilesStep(inputId, outputId) {
  const inputElement = document.getElementById(inputId);
  inputElement.disabled = false;

  const outputElement = document.getElementById(outputId);
  outputElement.innerHTML = '';

  const pickedPromise = new Promise((resolve) => {
    inputElement.addEventListener('change', (e) => {
      resolve(e.target.files);
    });
  });

  const cancel = document.createElement('button');
  inputElement.parentElement.appendChild(cancel);
  cancel.textContent = 'Cancel upload';
  const cancelPromise = new Promise((resolve) => {
    cancel.onclick = () => {
      resolve(null);
    };
  });

  // Wait for the user to pick the files.
  const files = yield {
    promise: Promise.race([pickedPromise, cancelPromise]),
    response: {
      action: 'starting',
    }
  };

  cancel.remove();

  // Disable the input element since further picks are not allowed.
  inputElement.disabled = true;

  if (!files) {
    return {
      response: {
        action: 'complete',
      }
    };
  }

  for (const file of files) {
    const li = document.createElement('li');
    li.append(span(file.name, {fontWeight: 'bold'}));
    li.append(span(
        `(${file.type || 'n/a'}) - ${file.size} bytes, ` +
        `last modified: ${
            file.lastModifiedDate ? file.lastModifiedDate.toLocaleDateString() :
                                    'n/a'} - `));
    const percent = span('0% done');
    li.appendChild(percent);

    outputElement.appendChild(li);

    const fileDataPromise = new Promise((resolve) => {
      const reader = new FileReader();
      reader.onload = (e) => {
        resolve(e.target.result);
      };
      reader.readAsArrayBuffer(file);
    });
    // Wait for the data to be ready.
    let fileData = yield {
      promise: fileDataPromise,
      response: {
        action: 'continue',
      }
    };

    // Use a chunked sending to avoid message size limits. See b/62115660.
    let position = 0;
    do {
      const length = Math.min(fileData.byteLength - position, MAX_PAYLOAD_SIZE);
      const chunk = new Uint8Array(fileData, position, length);
      position += length;

      const base64 = btoa(String.fromCharCode.apply(null, chunk));
      yield {
        response: {
          action: 'append',
          file: file.name,
          data: base64,
        },
      };

      let percentDone = fileData.byteLength === 0 ?
          100 :
          Math.round((position / fileData.byteLength) * 100);
      percent.textContent = `${percentDone}% done`;

    } while (position < fileData.byteLength);
  }

  // All done.
  yield {
    response: {
      action: 'complete',
    }
  };
}

scope.google = scope.google || {};
scope.google.colab = scope.google.colab || {};
scope.google.colab._files = {
  _uploadFiles,
  _uploadFilesContinue,
};
})(self);
 Saving naf.pdf to naf (1).pdf

✅ 'naf (1).pdf' uploaded successfully!

📄 3 pages | DPI=300 | Sharpen=2.0x | Contrast=1.5x

 ▶ Processing Page 1/3...
   ⚡ Page 1 inference completed in 8.47s

 ▶ Processing Page 2/3...
   ⚡ Page 2 inference completed in 8.72s

 ▶ Processing Page 3/3...
   ⚡ Page 3 inference completed in 8.37s

============================================================
🎉 Structured extraction done in 30.70s
============================================================
{
  "form_title": {
    "value": "Adamjee Life Assurance Co. Ltd - Window Takaful Operations - Needs Analysis Form",
    "confidence": 1.0
  },
  "family_takaful_need_analysis_of": {
    "value": "Syed Bilal Hussain",
    "confidence": 0.0
  },
  "section_1_basic_information": {
    "name": {
      "value": "Bilal Hussain",
      "confidence": 0.0
    },
    "address": {
      "value": "House # 91, Block C, Gulshan-e-Iqbal Karachi",
      "confidence": 0.0
    },
    "telephone": {
      "value": "+92-321-5678901",
      "confidence": 0.0
    },
    "email": {
      "value": "bilal.hussain@gmail.com",
      "confidence": 0.0
    },
    "date_of_birth": {
      "value": "20-11-1985",
      "confidence": 0.0
    },
    "marital_status": {
      "selected": "Married",
      "options": [
        "Single",
        "Married",
        "Widowed",
        "Divorced"
      ]
    },
    "state_of_health": {
      "selected": "",
      "options": [
        "Excellent",
        "Very Good",
        "Good",
        "Moderate",
        "Poor"
      ]
    },
    "smoker": {
      "selected": "",
      "options": [
        "Yes",
        "No"
      ]
    }
  },
  "section_2_family_details": {
    "number_of_dependents": {
      "value": "04",
      "confidence": 0.0
    },
    "dependents": [
      {
        "name": {
          "value": "Sana Bilal",
          "confidence": 0.0
        },
        "relationship": {
          "value": "Wife",
          "confidence": 0.0
        },
        "age": {
          "value": "36",
          "confidence": 0.0
        },
        "state_of_health": {
          "value": "Excellent",
          "confidence": 0.0
        },
        "occupation": {
          "value": "Doctor",
          "confidence": 0.0
        }
      },
      {
        "name": {
          "value": "Hamza Bilal",
          "confidence": 0.0
        },
        "relationship": {
          "value": "Son",
          "confidence": 0.0
        },
        "age": {
          "value": "10",
          "confidence": 0.0
        },
        "state_of_health": {
          "value": "Excellent",
          "confidence": 0.0
        },
        "occupation": {
          "value": "Student",
          "confidence": 0.0
        }
      },
      {
        "name": {
          "value": "Areeba Bilal",
          "confidence": 0.0
        },
        "relationship": {
          "value": "Daughter",
          "confidence": 0.0
        },
        "age": {
          "value": "7",
          "confidence": 0.0
        },
        "state_of_health": {
          "value": "V-Good",
          "confidence": 0.0
        },
        "occupation": {
          "value": "Student",
          "confidence": 0.0
        }
      },
      {
        "name": {
          "value": "Noor Bilal",
          "confidence": 0.0
        },
        "relationship": {
          "value": "Daughter",
          "confidence": 0.0
        },
        "age": {
          "value": "3",
          "confidence": 0.0
        },
        "state_of_health": {
          "value": "Good",
          "confidence": 0.0
        },
        "occupation": {
          "value": "Non-e",
          "confidence": 0.0
        }
      }
    ],
    "scope_for_family_expansion": {
      "selected": "",
      "options": [
        "Yes",
        "No"
      ]
    }
  },
  "section_3_employment_details": {
    "occupation": {
      "value": "",
      "confidence": 0.0
    },
    "length_of_service": {
      "value": "14 years",
      "confidence": 0.0
    },
    "annual_income": {
      "value": "4,200,000",
      "confidence": 0.0
    },
    "normal_retirement_age": {
      "value": "60 years",
      "confidence": 0.0
    },
    "covered_under_pension_scheme": {
      "selected": "",
      "options": [
        "Yes",
        "No"
      ]
    }
  },
  "section_4_financial_details": {
    "value_of_savings_and_assets": {
      "value": "28,000,000",
      "confidence": 0.0
    },
    "liabilities_outstanding_loans": {
      "value": "3,800,000",
      "confidence": 0.0
    },
    "expected_inheritance": {
      "value": "6,000,000",
      "confidence": 0.0
    }
  },
  "section_5_pension_details": {
    "employers_scheme_insurance_takaful": {
      "value": "HBL pension fund",
      "confidence": 0.0
    },
    "personal_premium_contribution": {
      "value": "360,000/year",
      "confidence": 0.0
    },
    "retirement_age": {
      "value": "60",
      "confidence": 0.0
    },
    "anticipated_value": {
      "value": "42,000,000",
      "confidence": 0.0
    }
  },
  "section_6_future_saving_needs": {
    "for_education_of_children": {
      "value": "12,000,000",
      "confidence": 0.0
    },
    "for_wedding": {
      "value": "7,000,000",
      "confidence": 0.0
    },
    "for_house_purchase": {
      "value": "Not required",
      "confidence": 0.0
    },
    "others": {
      "value": "2,000,000 Vacation Fund.",
      "confidence": 0.0
    }
  },
  "section_7_existing_plans": [
    {
      "company_takaful_operator": {
        "value": "Adamjee Family",
        "confidence": 0.0
      },
      "policy_certificate_no": {
        "value": "A/T-662541",
        "confidence": 0.0
      },
      "sum_assured_covered": {
        "value": "8,000,000",
        "confidence": 0.0
      },
      "premium_contribution": {
        "value": "120,000",
        "confidence": 0.0
      },
      "start_date": {
        "value": "15-05-20",
        "confidence": 0.0
      },
      "maturity_date": {
        "value": "15-05-45",
        "confidence": 0.0
      },
      "purpose": {
        "value": "Family",
        "confidence": 0.0
      }
    },
    {
      "company_takaful_operator": {
        "value": "EFU Life",
        "confidence": 0.0
      },
      "policy_certificate_no": {
        "value": "EFU-458822",
        "confidence": 0.0
      },
      "sum_assured_covered": {
        "value": "3,000,000",
        "confidence": 0.0
      },
      "premium_contribution": {
        "value": "55,000",
        "confidence": 0.0
      },
      "start_date": {
        "value": "12-09-17",
        "confidence": 0.0
      },
      "maturity_date": {
        "value": "12-09-37",
        "confidence": 0.0
      },
      "purpose": {
        "value": "Saving",
        "confidence": 0.0
      }
    }
  ],
  "section_8_financial_priorities": {
    "financial_security_event_of_death": {
      "value": "",
      "confidence": 0.0
    },
    "financial_security_critical_illness": {
      "value": "",
      "confidence": 0.0
    },
    "providing_retirement_income": {
      "value": "",
      "confidence": 0.0
    },
    "planning_childrens_education": {
      "value": "",
      "confidence": 0.0
    },
    "planning_childrens_wedding": {
      "value": "",
      "confidence": 0.0
    },
    "building_capital_regular_saving": {
      "value": "",
      "confidence": 0.0
    },
    "investing_capital_better_return": {
      "value": "6",
      "confidence": 0.0
    },
    "investment_horizon": {
      "selected": "Short term (<1 yr)",
      "options": [
        "Short term (<1 yr)",
        "Medium term (1-5 yrs)",
        "Long term (>5 yrs)"
      ]
    },
    "investment_knowledge_level": {
      "selected": "",
      "options": [
        "Little knowledge",
        "Some knowledge",
        "Both knowledge & experienced"
      ]
    },
    "current_financial_position": {
      "selected": "",
      "options": [
        "Very secure",
        "Somewhat secure",
        "Not sure",
        "Likely worse"
      ]
    }
  },
  "section_9_identified_takaful_needs": {
    "life_insurance_death_maturity": {
      "value": "Comprehensive Family Protection",
      "confidence": 0.0
    },
    "desirable_sum_covered": {
      "value": "30,000,000",
      "confidence": 0.0
    },
    "health_family_takaful": {
      "value": "Premium Health",
      "confidence": 0.0
    },
    "desirable_limit_coverage_per_annum": {
      "value": "30,000,000",
      "confidence": 0.0
    },
    "saving_investment_planning": {
      "value": "Education + Retirement",
      "confidence": 0.0
    },
    "desirable_returns_per_annum": {
      "value": "11.4",
      "confidence": 0.0
    },
    "pension_planning": {
      "selected": "Yes",
      "options": [
        "Yes",
        "No"
      ]
    },
    "desirable_pension_per_annum": {
      "value": "3,000,000",
      "confidence": 0.0
    }
  },
  "section_10_additional_information": {
    "value": "",
    "confidence": 0.0
  },
  "section_11_recommendation": {
    "life_stage": {
      "selected": "",
      "options": [
        "Childhood",
        "Young unmarried",
        "Young married",
        "Young married w/ children",
        "Married w/ older children",
        "Post-family",
        "Pre-retirement",
        "Retirement"
      ]
    },
    "protection_needs": {
      "selected": "",
      "options": [
        "Life & Health",
        "Savings & Investment",
        "Pension"
      ]
    },
    "appetite_for_risk": {
      "selected": "",
      "options": [
        "Low",
        "Medium",
        "High"
      ]
    },
    "plan_recommended": {
      "value": "Family Takaful Plan (Elite)",
      "confidence": 0.0
    },
    "commitment_current_future_years": {
      "value": "20 years",
      "confidence": 0.0
    },
    "all_risks_charges_explained": {
      "selected": "",
      "options": [
        "Yes",
        "No"
      ]
    },
    "why_plan_most_suited": {
      "value": "High protection with education and retirement",
      "confidence": 0.0
    }
  },
  "sales_officer_certification": {
    "statement": {
      "value": "",
      "confidence": 0.0
    },
    "date": {
      "value": "15-07-2026",
      "confidence": 0.0
    },
    "name": {
      "value": "Imran Ali",
      "confidence": 0.0
    },
    "signature": {
      "value": "",
      "confidence": 0.0
    }
  },
  "prospect_acknowledgement": {
    "statement": {
      "value": "",
      "confidence": 0.0
    },
    "acknowledgements": {
      "a": {
        "value": "",
        "confidence": 0.0
      },
      "b": {
        "value": "",
        "confidence": 0.0
      },
      "c": {
        "value": "",
        "confidence": 0.0
      },
      "d": {
        "value": "",
        "confidence": 0.0
      },
      "e": {
        "value": "",
        "confidence": 0.0
      },
      "f": {
        "value": "",
        "confidence": 0.0
      },
      "g": {
        "value": "",
        "confidence": 0.0
      }
    },
    "date": {
      "value": "",
      "confidence": 0.0
    },
    "signature": {
      "value": "",
      "confidence": 0.0
    }
  }
}
