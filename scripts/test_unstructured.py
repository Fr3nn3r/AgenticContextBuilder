from unstructured.partition.pdf import partition_pdf

elements = partition_pdf(
    r"datasets\01-Claims-Travel-Canada\Customer 16\Customer 16---Summary__250129-025548.pdf",
    strategy="fast",  # Use fast strategy to avoid poppler dependency
    infer_table_structure=False,  # Disable table parsing for simplicity
    extract_images_in_pdf=False,  # tweak as needed
    # NOTE: do NOT set partition_by_api; defaults to local
)

# Print all the results
print(f"Found {len(elements)} elements in the PDF:")
print("=" * 50)

for i, element in enumerate(elements):
    print(f"{i+1}. {type(element).__name__}: {str(element)}")
    print("-" * 30)
