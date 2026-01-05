"""
Dynamic Claims Processing Application - Schema-Driven Architecture

This Streamlit application demonstrates the CTO's schema-driven directive:
- Load any policy's schema and logic JSON files
- Dynamically render forms (no hardcoded fields)
- Execute rules via IEvaluator interface
- Display rich results

Success Criteria:
If given a new "Pet Insurance Policy" JSON with completely different fields,
this application should work WITHOUT any code changes.

Usage:
    streamlit run src/policy_compiler/runtime/streamlit_app.py
"""

import streamlit as st
from pathlib import Path
import json

from policy_compiler.runtime.schema_loader import load_schema, load_logic, SchemaLoadError
from policy_compiler.runtime.widget_factory import render_section, WidgetFactory
from policy_compiler.runtime.claim_mapper import SchemaBasedClaimMapper
from policy_compiler.runtime.evaluator import NeuroSymbolicEvaluator
from policy_compiler.runtime.result_interpreter import ResultInterpreter


# Page configuration
st.set_page_config(
    page_title="Schema-Driven Claims Processor",
    page_icon="[OK]",
    layout="wide"
)

# Title
st.title("Schema-Driven Claims Processing System")
st.markdown("---")


# Sidebar: File Selection
st.sidebar.header("Policy Configuration")
st.sidebar.markdown("Select a policy to load its configuration automatically.")

# Initialize session state
if "schema" not in st.session_state:
    st.session_state.schema = None
if "logic" not in st.session_state:
    st.session_state.logic = None
if "symbol_table" not in st.session_state:
    st.session_state.symbol_table = None
if "flat_claim_data" not in st.session_state:
    st.session_state.flat_claim_data = {}
if "result" not in st.session_state:
    st.session_state.result = None


# Scan output/ui-data for available policies
ui_data_dir = Path("output/ui-data")
available_policies = []

if ui_data_dir.exists():
    # Find all *_logic.json files (excluding *_normalized_logic.json)
    logic_files = sorted([
        f for f in ui_data_dir.glob("*_logic.json")
        if not f.name.endswith("_normalized_logic.json")
    ])

    # Extract policy names (remove _logic.json suffix)
    available_policies = [f.stem.replace("_logic", "") for f in logic_files]

# Policy selection dropdown
if available_policies:
    # Add empty option at the beginning
    policy_options = ["Select a policy..."] + available_policies

    selected_policy = st.sidebar.selectbox(
        "Available Policies",
        options=policy_options,
        index=0
    )

    # Load button (only enabled if a policy is selected)
    if selected_policy != "Select a policy...":
        if st.sidebar.button("Load Selected Policy", type="primary", use_container_width=True):
            try:
                # Construct file paths
                policy_base = selected_policy
                logic_path = ui_data_dir / f"{policy_base}_logic.json"
                schema_path = ui_data_dir / f"{policy_base}_form_schema.json"
                symbol_table_path = ui_data_dir / f"{policy_base}_symbol_table.json"

                # Load logic file
                st.session_state.logic = load_logic(str(logic_path))

                # Load schema file
                if schema_path.exists():
                    st.session_state.schema = load_schema(str(schema_path))
                else:
                    st.sidebar.error(f"Schema file not found: {schema_path.name}")
                    st.stop()

                # Load symbol table file (optional)
                if symbol_table_path.exists():
                    try:
                        with open(symbol_table_path, "r", encoding="utf-8") as f:
                            st.session_state.symbol_table = json.load(f)
                        st.sidebar.success(f"Symbol table loaded")
                    except Exception as e:
                        st.sidebar.warning(f"Symbol table found but failed to load: {e}")
                        st.session_state.symbol_table = None
                else:
                    st.sidebar.warning(f"Symbol table not found (optional)")
                    st.session_state.symbol_table = None

                # Reset claim data and result
                st.session_state.flat_claim_data = {}
                st.session_state.result = None

                # Display policy info
                policy_id = st.session_state.schema.get("policy_id", "Unknown")
                total_fields = st.session_state.schema.get("statistics", {}).get("total_fields", 0)
                total_rules = st.session_state.logic.get("transpiled_data", {}).get("_total_rules", 0)

                st.sidebar.success("Policy loaded successfully!")
                st.sidebar.info(f"""
**Policy:** {policy_id}
**Fields:** {total_fields}
**Rules:** {total_rules}
                """)

            except SchemaLoadError as e:
                st.sidebar.error(f"Error loading files: {e}")
            except Exception as e:
                st.sidebar.error(f"Unexpected error: {e}")
else:
    st.sidebar.warning(f"No policies found in {ui_data_dir}")
    st.sidebar.info("Please ensure policy files are in output/ui-data/")


# Main content
if st.session_state.schema is None or st.session_state.logic is None:
    st.info("Please load a policy configuration using the sidebar.")
    st.stop()


# Display policy information
policy_id = st.session_state.schema.get("policy_id", "Unknown Policy")
st.header(f"Policy: {policy_id}")

# Form rendering
st.subheader("Claim Information")
st.markdown("Fill out the form below. Fields marked with * are required.")

sections = st.session_state.schema.get("sections", {})

# Extract currency from policy
currency = WidgetFactory.extract_currency_from_policy(
    st.session_state.schema,
    st.session_state.logic
)

# Render sections in order
sorted_sections = sorted(
    sections.items(),
    key=lambda x: x[1].get("order", 999)
)

for section_name, section_data in sorted_sections:
    render_section(
        section_name,
        section_data,
        st.session_state.flat_claim_data,
        currency=currency,
        symbol_table=st.session_state.symbol_table
    )


# Validation and submission
st.markdown("---")
col1, col2, col3 = st.columns([1, 1, 2])

with col1:
    if st.button("Validate Data", use_container_width=True):
        # Validate using ClaimMapper
        mapper = SchemaBasedClaimMapper()
        errors = mapper.validate(st.session_state.flat_claim_data, st.session_state.schema)

        if errors:
            st.error(f"Validation failed with {len(errors)} error(s):")
            for error in errors:
                st.error(f"- {error}")
        else:
            st.success("All data is valid!")

with col2:
    if st.button("Submit & Evaluate", type="primary", use_container_width=True):
        # Validate
        mapper = SchemaBasedClaimMapper()
        errors = mapper.validate(st.session_state.flat_claim_data, st.session_state.schema)

        if errors:
            st.error(f"Validation failed with {len(errors)} error(s):")
            for error in errors:
                st.error(f"- {error}")
        else:
            # Inflate flat data to nested structure
            nested_claim_data = mapper.inflate(
                st.session_state.flat_claim_data,
                st.session_state.schema
            )

            # Evaluate using rules engine
            evaluator = NeuroSymbolicEvaluator()
            raw_result = evaluator.evaluate(
                st.session_state.logic,
                nested_claim_data
            )

            # Interpret result
            interpreter = ResultInterpreter()
            rich_result = interpreter.interpret(raw_result, st.session_state.logic)

            # Store result
            st.session_state.result = rich_result

            st.success("Evaluation complete!")
            st.rerun()


# Display result if available
if st.session_state.result:
    st.markdown("---")
    st.header("Evaluation Result")

    result = st.session_state.result
    summary = result.get("summary", {})
    financials = result.get("financials", {})
    reasoning_trace = result.get("reasoning_trace", {})
    metadata = result.get("metadata", {})

    # Summary section with color coding
    status = summary.get("status", "UNKNOWN")
    message = summary.get("primary_message", "No message")
    color_code = summary.get("color_code", "gray")

    color_map = {
        "green": "#28a745",
        "red": "#dc3545",
        "orange": "#fd7e14",
        "gray": "#6c757d"
    }

    st.markdown(f"""
    <div style="padding: 20px; border-radius: 10px; background-color: {color_map.get(color_code, '#6c757d')}; color: white;">
        <h2 style="margin: 0; color: white;">Status: {status}</h2>
        <p style="margin: 10px 0 0 0; font-size: 18px;">{message}</p>
    </div>
    """, unsafe_allow_html=True)

    # Financials section
    st.subheader("Coverage Details")
    col1, col2 = st.columns(2)

    with col1:
        limit = financials.get("applicable_limit")
        if limit:
            st.metric(
                label=limit.get("category", "Coverage Limit"),
                value=f"{limit.get('currency', 'CAD')} ${limit.get('amount', 0):,.2f}"
            )
        else:
            st.info("No coverage limit determined")

    with col2:
        deductible = financials.get("applicable_deductible")
        if deductible:
            st.metric(
                label="Deductible",
                value=f"{deductible.get('currency', 'CAD')} ${deductible.get('amount', 0):,.2f}"
            )
        else:
            st.info("No deductible applicable")

    # Reasoning trace
    st.subheader("Reasoning Trace")

    triggers = reasoning_trace.get("triggers", [])
    red_flags = reasoning_trace.get("red_flags", [])

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**[OK] Conditions Met**")
        if triggers:
            for trigger in triggers:
                with st.expander(f"[OK] {trigger.get('rule_name', 'Unknown')}"):
                    st.write(trigger.get("description", "No description"))
        else:
            st.info("No conditions evaluated")

    with col2:
        st.markdown("**[X] Exclusions / Issues**")
        if red_flags:
            for flag in red_flags:
                with st.expander(f"[X] {flag.get('rule_name', 'Unknown')}"):
                    st.write(flag.get("description", "No description"))
        else:
            st.success("No exclusions triggered")

    # Metadata
    with st.expander("Execution Metadata"):
        st.json(metadata)

    # Raw data inspection
    with st.expander("Raw Data (Debug)"):
        st.subheader("Flat Claim Data (UI)")
        st.json(st.session_state.flat_claim_data)

        st.subheader("Nested Claim Data (Engine)")
        mapper = SchemaBasedClaimMapper()
        nested = mapper.inflate(st.session_state.flat_claim_data, st.session_state.schema)
        st.json(nested)

        st.subheader("Full Result")
        st.json(st.session_state.result)


# Footer
st.markdown("---")
st.markdown("""
**Schema-Driven Architecture**
This application requires ZERO code changes to support new policy types.
Simply load new schema and logic JSON files to process different insurance products.
""")
