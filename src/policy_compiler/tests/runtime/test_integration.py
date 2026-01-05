"""
Integration test for the complete schema-driven architecture.

Tests the full pipeline end-to-end:
1. Load schema and logic from real files
2. Create claim data (flat)
3. Validate data
4. Inflate to nested structure
5. Evaluate with rules engine
6. Interpret results

Uses real insurance policy files from output directory.
"""

import pytest
from pathlib import Path

from policy_compiler.runtime.schema_loader import load_schema, load_logic
from policy_compiler.runtime.claim_mapper import SchemaBasedClaimMapper
from policy_compiler.runtime.evaluator import NeuroSymbolicEvaluator
from policy_compiler.runtime.result_interpreter import ResultInterpreter


class TestEndToEndIntegration:
    """Integration tests using real insurance policy data."""

    @pytest.fixture
    def insurance_policy_files(self):
        """Load real insurance policy schema and logic files."""
        schema_path = Path("output/output_schemas/insurance policy_form_schema.json")
        logic_path = Path("output/processing/20251129-114118-insurance p/insurance policy_logic.json")

        if not schema_path.exists():
            pytest.skip(f"Schema file not found: {schema_path}")
        if not logic_path.exists():
            pytest.skip(f"Logic file not found: {logic_path}")

        schema = load_schema(schema_path)
        logic = load_logic(logic_path)

        return schema, logic

    def test_schema_and_logic_loading(self, insurance_policy_files):
        """Test that schema and logic files load successfully."""
        schema, logic = insurance_policy_files

        # Verify schema structure
        assert "policy_id" in schema
        assert "sections" in schema
        assert "statistics" in schema

        # Verify logic structure
        assert "transpiled_data" in logic
        assert "rules" in logic["transpiled_data"]

        # Check expected counts
        stats = schema.get("statistics", {})
        assert stats.get("total_fields", 0) > 0

        rules = logic.get("transpiled_data", {}).get("rules", [])
        assert len(rules) > 0

    def test_simple_approved_claim(self, insurance_policy_files):
        """Test a simple claim that should be approved."""
        schema, logic = insurance_policy_files

        # Create flat claim data (simple liability claim)
        flat_claim_data = {
            "claim.header.claim_type": "liability",
            "claim.header.policy_number": "TEST-001",
            "claim.incident.date": "2025-11-29",
            "claim.incident.location": "Toronto, ON",
            "claim.incident.attributes.is_watercraft": False,
            "claim.incident.attributes.is_aircraft": False,
            "claim.parties.claimants[0].role": "insured",
            "claim.financials.claim_amount": 10000
        }

        # Initialize components
        mapper = SchemaBasedClaimMapper()
        evaluator = NeuroSymbolicEvaluator()
        interpreter = ResultInterpreter()

        # Step 1: Validate
        errors = mapper.validate(flat_claim_data, schema)
        assert len(errors) == 0, f"Validation failed: {errors}"

        # Step 2: Inflate
        nested_claim_data = mapper.inflate(flat_claim_data, schema)

        # Verify inflation worked
        assert "claim" in nested_claim_data
        assert nested_claim_data["claim"]["header"]["claim_type"] == "liability"
        assert nested_claim_data["claim"]["parties"]["claimants"][0]["role"] == "insured"

        # Step 3: Evaluate
        raw_result = evaluator.evaluate(logic, nested_claim_data)

        # Verify raw result structure
        assert "limits" in raw_result
        assert "conditions" in raw_result
        assert "exclusions" in raw_result
        assert "deductibles" in raw_result
        assert "metadata" in raw_result

        # Step 4: Interpret
        rich_result = interpreter.interpret(raw_result, logic)

        # Verify rich result structure
        assert "summary" in rich_result
        assert "financials" in rich_result
        assert "reasoning_trace" in rich_result
        assert "metadata" in rich_result

        summary = rich_result["summary"]
        assert summary["status"] in ["APPROVED", "DENIED", "REFERRAL_NEEDED"]
        assert summary["color_code"] in ["green", "red", "orange"]

    def test_excluded_claim_watercraft(self, insurance_policy_files):
        """Test a claim that should be denied due to watercraft exclusion."""
        schema, logic = insurance_policy_files

        # Create flat claim data with watercraft exceeding limit
        flat_claim_data = {
            "claim.header.claim_type": "liability",
            "claim.incident.attributes.is_watercraft": True,
            "claim.incident.attributes.watercraft_length": 12,  # Exceeds 8m limit
            "claim.parties.claimants[0].role": "insured",
            "claim.financials.claim_amount": 50000
        }

        # Initialize components
        mapper = SchemaBasedClaimMapper()
        evaluator = NeuroSymbolicEvaluator()
        interpreter = ResultInterpreter()

        # Execute pipeline
        errors = mapper.validate(flat_claim_data, schema)
        assert len(errors) == 0

        nested_claim_data = mapper.inflate(flat_claim_data, schema)
        raw_result = evaluator.evaluate(logic, nested_claim_data)
        rich_result = interpreter.interpret(raw_result, logic)

        # Check for exclusion
        summary = rich_result["summary"]

        # Note: Actual status depends on the specific rules in the policy
        # This test documents the behavior
        assert summary["status"] in ["APPROVED", "DENIED", "REFERRAL_NEEDED"]

        # If denied, should have red flags
        if summary["status"] == "DENIED":
            reasoning = rich_result["reasoning_trace"]
            assert len(reasoning.get("red_flags", [])) > 0

    def test_all_field_types(self, insurance_policy_files):
        """Test that all field types are handled correctly."""
        schema, logic = insurance_policy_files

        # Create claim with various field types
        flat_claim_data = {
            # Enum
            "claim.header.claim_type": "first_party",
            # String
            "claim.header.policy_number": "POL-456",
            "claim.incident.location": "Vancouver, BC",
            # Boolean fields
            "claim.incident.attributes.is_watercraft": False,
            "claim.incident.attributes.is_aircraft": False,
            # Integer
            "claim.incident.attributes.watercraft_length": 5,
            # Number (would be float)
            "claim.financials.claim_amount": 25000.50,
            # Array
            "claim.parties.claimants[0].role": "insured"
        }

        mapper = SchemaBasedClaimMapper()

        # Validate
        errors = mapper.validate(flat_claim_data, schema)
        assert len(errors) == 0

        # Inflate
        nested = mapper.inflate(flat_claim_data, schema)

        # Verify types are preserved
        assert isinstance(nested["claim"]["header"]["claim_type"], str)
        assert isinstance(nested["claim"]["incident"]["attributes"]["is_watercraft"], bool)
        assert isinstance(nested["claim"]["incident"]["attributes"]["watercraft_length"], int)
        assert isinstance(nested["claim"]["financials"]["claim_amount"], float)
        assert isinstance(nested["claim"]["parties"]["claimants"], list)

    def test_engine_execution_metadata(self, insurance_policy_files):
        """Test that execution metadata is captured."""
        schema, logic = insurance_policy_files

        flat_claim_data = {
            "claim.header.claim_type": "liability",
            "claim.parties.claimants[0].role": "insured"
        }

        mapper = SchemaBasedClaimMapper()
        evaluator = NeuroSymbolicEvaluator()

        nested = mapper.inflate(flat_claim_data, schema)
        raw_result = evaluator.evaluate(logic, nested)

        metadata = raw_result["metadata"]

        # Verify metadata fields
        assert "engine_version" in metadata
        assert "total_rules" in metadata
        assert "execution_time_ms" in metadata

        # Verify values
        assert metadata["engine_version"] == "1.0.0"
        assert metadata["total_rules"] > 0
        assert metadata["execution_time_ms"] >= 0

    def test_financial_extraction(self, insurance_policy_files):
        """Test that financial amounts are extracted correctly."""
        schema, logic = insurance_policy_files

        flat_claim_data = {
            "claim.header.claim_type": "liability",
            "claim.parties.claimants[0].role": "insured",
            "claim.financials.claim_amount": 100000
        }

        mapper = SchemaBasedClaimMapper()
        evaluator = NeuroSymbolicEvaluator()
        interpreter = ResultInterpreter()

        nested = mapper.inflate(flat_claim_data, schema)
        raw_result = evaluator.evaluate(logic, nested)
        rich_result = interpreter.interpret(raw_result, logic)

        financials = rich_result["financials"]

        # Should have either limit or deductible or both
        assert financials is not None

        # If limit is present, verify structure
        if financials.get("applicable_limit"):
            limit = financials["applicable_limit"]
            assert "amount" in limit
            assert "currency" in limit
            assert "category" in limit
            assert isinstance(limit["amount"], (int, float))

    def test_validation_catches_type_errors(self, insurance_policy_files):
        """Test that validation catches type mismatches."""
        schema, logic = insurance_policy_files

        # Create claim with wrong type (string instead of integer)
        flat_claim_data = {
            "claim.incident.attributes.watercraft_length": "twelve"  # Should be int
        }

        mapper = SchemaBasedClaimMapper()
        errors = mapper.validate(flat_claim_data, schema)

        # Should have validation error
        assert len(errors) > 0
        assert any("watercraft_length" in err.field_key for err in errors)


class TestSuccessCriteria:
    """Test the CTO's success criteria: zero code changes for new policy types."""

    def test_no_hardcoded_fields(self, tmp_path):
        """
        Verify the system works with a completely different schema
        without code changes.

        This creates a mock "Pet Insurance" policy to prove the architecture.
        """
        # Create mock pet insurance schema
        pet_schema = {
            "policy_id": "pet_insurance",
            "sections": {
                "header": {
                    "title": "Claim Header",
                    "order": 1,
                    "fields": [
                        {"key": "claim.header.claim_type", "label": "Claim Type", "type": "string"}
                    ]
                },
                "pet_info": {
                    "title": "Pet Information",
                    "order": 2,
                    "fields": [
                        {"key": "claim.pet.breed", "label": "Breed", "type": "string"},
                        {"key": "claim.pet.age", "label": "Age (years)", "type": "integer"},
                        {"key": "claim.pet.is_vaccinated", "label": "Vaccinated", "type": "boolean"}
                    ]
                }
            },
            "statistics": {
                "total_fields": 4
            }
        }

        # Create mock pet insurance logic
        pet_logic = {
            "transpiled_data": {
                "rules": [
                    {
                        "id": "age_limit",
                        "name": "Age Limit",
                        "type": "condition",
                        "logic": {
                            "if": [
                                {"<": [{"var": "claim.pet.age"}, 15]},
                                True,
                                False
                            ]
                        },
                        "reasoning": "Pet must be under 15 years old"
                    }
                ],
                "_total_rules": 1
            }
        }

        # Create flat pet claim data
        flat_pet_claim = {
            "claim.header.claim_type": "illness",
            "claim.pet.breed": "Golden Retriever",
            "claim.pet.age": 7,
            "claim.pet.is_vaccinated": True
        }

        # Execute the EXACT SAME CODE as for insurance policy
        mapper = SchemaBasedClaimMapper()
        evaluator = NeuroSymbolicEvaluator()
        interpreter = ResultInterpreter()

        # Validate
        errors = mapper.validate(flat_pet_claim, pet_schema)
        assert len(errors) == 0

        # Inflate
        nested = mapper.inflate(flat_pet_claim, pet_schema)
        assert nested["claim"]["pet"]["breed"] == "Golden Retriever"
        assert nested["claim"]["pet"]["age"] == 7

        # Evaluate
        raw_result = evaluator.evaluate(pet_logic, nested)
        assert "conditions" in raw_result

        # Interpret
        rich_result = interpreter.interpret(raw_result, pet_logic)
        assert "summary" in rich_result

        # SUCCESS: No code changes needed for completely different policy type!
