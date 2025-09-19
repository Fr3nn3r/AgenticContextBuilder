#!/usr/bin/env python3

import os
import json
import hashlib
import stat
from datetime import datetime
from pathlib import Path
import argparse
import mimetypes
import shutil
import random

def get_file_hash(file_path, algorithm='sha256'):
    """Calculate file hash using specified algorithm."""
    hash_obj = hashlib.new(algorithm)
    try:
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_obj.update(chunk)
        return hash_obj.hexdigest()
    except (OSError, IOError):
        return None

def extract_file_metadata(file_path):
    """Extract comprehensive metadata from a file."""
    try:
        file_stat = os.stat(file_path)
        file_path_obj = Path(file_path)
        
        # Basic file information
        metadata = {
            'file_name': file_path_obj.name,
            'file_path': str(file_path_obj.absolute()),
            'file_extension': file_path_obj.suffix,
            'file_size_bytes': file_stat.st_size,
            'file_size_human': format_bytes(file_stat.st_size),
        }
        
        # Timestamps
        metadata.update({
            'created_time': datetime.fromtimestamp(file_stat.st_ctime).isoformat(),
            'modified_time': datetime.fromtimestamp(file_stat.st_mtime).isoformat(),
            'accessed_time': datetime.fromtimestamp(file_stat.st_atime).isoformat(),
        })
        
        # File permissions and attributes
        metadata.update({
            'permissions': {
                'octal': oct(stat.S_IMODE(file_stat.st_mode)),
                'readable': os.access(file_path, os.R_OK),
                'writable': os.access(file_path, os.W_OK),
                'executable': os.access(file_path, os.X_OK),
            },
            'is_directory': file_path_obj.is_dir(),
            'is_file': file_path_obj.is_file(),
            'is_symlink': file_path_obj.is_symlink(),
        })
        
        # MIME type
        mime_type, encoding = mimetypes.guess_type(file_path)
        metadata.update({
            'mime_type': mime_type,
            'encoding': encoding,
        })
        
        # File hashes (only for regular files, not directories)
        if file_path_obj.is_file():
            metadata.update({
                'hashes': {
                    'md5': get_file_hash(file_path, 'md5'),
                    'sha1': get_file_hash(file_path, 'sha1'),
                    'sha256': get_file_hash(file_path, 'sha256'),
                }
            })
        
        # Windows-specific attributes (if on Windows)
        if os.name == 'nt':
            metadata['windows_attributes'] = {
                'hidden': bool(file_stat.st_file_attributes & stat.FILE_ATTRIBUTE_HIDDEN) if hasattr(file_stat, 'st_file_attributes') else None,
                'system': bool(file_stat.st_file_attributes & stat.FILE_ATTRIBUTE_SYSTEM) if hasattr(file_stat, 'st_file_attributes') else None,
                'archive': bool(file_stat.st_file_attributes & stat.FILE_ATTRIBUTE_ARCHIVE) if hasattr(file_stat, 'st_file_attributes') else None,
            }
        
        return metadata
        
    except (OSError, IOError) as e:
        return {
            'file_name': Path(file_path).name,
            'file_path': str(Path(file_path).absolute()),
            'error': str(e),
            'metadata_extraction_failed': True
        }

def format_bytes(bytes_value):
    """Convert bytes to human readable format."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.2f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.2f} PB"

def generate_extraction_id(input_folder):
    """Generate unique extraction ID with timestamp format: ingest-2025-09-19-XXXXXXXXXX-input_folder"""
    current_date = datetime.now().strftime("%Y-%m-%d")
    random_suffix = ''.join([str(random.randint(0, 9)) for _ in range(10)])
    input_folder_name = Path(input_folder).name
    return f"ingest-{current_date}-{random_suffix}-{input_folder_name}"

def process_dataset_folder(dataset_path, output_base_path, extraction_id, subfolders_filter=None):
    """Process a single dataset folder and create individual metadata files."""
    dataset_name = Path(dataset_path).name
    dataset_folder_name = f"dataset-{dataset_name}"
    output_dataset_path = Path(output_base_path) / extraction_id / dataset_folder_name

    # Create output directory structure
    output_dataset_path.mkdir(parents=True, exist_ok=True)

    processed_files = []

    # Process all files in the dataset folder (recursively)
    for item in Path(dataset_path).rglob('*'):
        if item.is_file():
            relative_path = item.relative_to(dataset_path)

            # If subfolders filter is specified, check if file is in allowed subfolder
            if subfolders_filter:
                # Get the top-level folder name for this file
                top_level_folder = relative_path.parts[0] if relative_path.parts else None
                if top_level_folder not in subfolders_filter:
                    continue  # Skip files not in specified subfolders

            print(f"  Processing file: {relative_path}")

            # Extract metadata
            metadata = extract_file_metadata(item)
            
            # Add processing information
            processing_info = {
                'extraction_time': datetime.now().isoformat(),
                'extraction_id': extraction_id,
                'source_dataset': dataset_name,
                'dataset_folder_name': dataset_folder_name,
                'output_path': str(output_dataset_path),
            }
            
            # Combine metadata with processing info
            file_metadata = {
                'processing_info': processing_info,
                'file_metadata': metadata
            }
            
            # Create individual metadata file (preserve relative path structure)
            relative_path_parent = relative_path.parent
            metadata_filename = f"{item.stem}_metadata.json"
            metadata_output_dir = output_dataset_path / relative_path_parent
            metadata_output_dir.mkdir(parents=True, exist_ok=True)
            metadata_file_path = metadata_output_dir / metadata_filename
            
            # Write metadata to individual file
            with open(metadata_file_path, 'w', encoding='utf-8') as f:
                json.dump(file_metadata, f, indent=2, ensure_ascii=False)
            
            processed_files.append({
                'original_file': str(item),
                'relative_path': str(relative_path),
                'metadata_file': str(metadata_file_path),
                'file_name': item.name,
                'metadata_filename': metadata_filename
            })
    
    # Create a summary file for the dataset
    dataset_summary = {
        'dataset_info': {
            'extraction_id': extraction_id,
            'dataset_name': dataset_name,
            'dataset_folder_name': dataset_folder_name,
            'source_path': str(dataset_path),
            'output_path': str(output_dataset_path),
            'processing_time': datetime.now().isoformat(),
            'total_files_processed': len(processed_files),
        },
        'processed_files': processed_files
    }
    
    summary_file_path = output_dataset_path / f"{dataset_name}_summary.json"
    with open(summary_file_path, 'w', encoding='utf-8') as f:
        json.dump(dataset_summary, f, indent=2, ensure_ascii=False)
    
    print(f"  Created summary: {summary_file_path}")
    return len(processed_files)

def main():
    parser = argparse.ArgumentParser(
        description='Extract metadata from dataset files with mirrored folder structure'
    )
    parser.add_argument(
        'input_folder',
        help='Path to the input datasets folder'
    )
    parser.add_argument(
        'output_folder',
        help='Path to the output folder for metadata files'
    )
    parser.add_argument(
        '-n', '--num-datasets',
        type=int,
        default=3,
        help='Number of datasets to process (default: 3)'
    )
    parser.add_argument(
        '-d', '--datasets',
        nargs='*',
        help='Specific dataset names to process (optional, processes all by default)'
    )
    parser.add_argument(
        '-s', '--subfolders',
        nargs='*',
        help='Specific subfolders within datasets to process (optional, processes all by default)'
    )
    
    args = parser.parse_args()

    input_path = Path(args.input_folder)
    output_path = Path(args.output_folder)

    if not input_path.exists():
        print(f"Error: Input folder does not exist: {input_path}")
        return 1

    if not input_path.is_dir():
        print(f"Error: Input path is not a directory: {input_path}")
        return 1

    # Generate unique extraction ID
    extraction_id = generate_extraction_id(input_path)
    print(f"Extraction ID: {extraction_id}")

    # Create output directory
    output_path.mkdir(parents=True, exist_ok=True)

    # Get list of dataset folders (directories only)
    dataset_folders = [d for d in input_path.iterdir() if d.is_dir()]
    dataset_folders.sort()  # Sort for consistent ordering

    if not dataset_folders:
        print(f"No dataset folders found in {input_path}")
        return 1

    # Filter datasets if specific ones are requested
    if args.datasets:
        requested_datasets = set(args.datasets)
        available_datasets = {d.name for d in dataset_folders}

        # Check if all requested datasets exist
        missing_datasets = requested_datasets - available_datasets
        if missing_datasets:
            print(f"Warning: Requested datasets not found: {', '.join(missing_datasets)}")

        # Filter to only requested datasets that exist
        dataset_folders = [d for d in dataset_folders if d.name in requested_datasets]

        if not dataset_folders:
            print("No valid datasets found from the requested list")
            return 1

        datasets_to_process = dataset_folders
    else:
        # Process first N datasets if no specific datasets requested
        datasets_to_process = dataset_folders[:args.num_datasets]
    
    print(f"Processing {len(datasets_to_process)} datasets from {input_path}")
    print(f"Output will be saved to: {output_path}")
    print()
    
    total_files_processed = 0
    
    for i, dataset_folder in enumerate(datasets_to_process, 1):
        print(f"[{i}/{len(datasets_to_process)}] Processing dataset: {dataset_folder.name}")

        try:
            files_processed = process_dataset_folder(dataset_folder, output_path, extraction_id, args.subfolders)
            total_files_processed += files_processed
            print(f"  [OK] Processed {files_processed} files")
        except Exception as e:
            print(f"  [ERROR] Error processing dataset {dataset_folder.name}: {e}")

        print()
    
    # Create overall summary
    overall_summary = {
        'extraction_summary': {
            'extraction_id': extraction_id,
            'input_folder': str(input_path),
            'output_folder': str(output_path),
            'processing_time': datetime.now().isoformat(),
            'datasets_requested': args.num_datasets if not args.datasets else None,
            'specific_datasets_requested': args.datasets if args.datasets else None,
            'specific_subfolders_requested': args.subfolders if args.subfolders else None,
            'datasets_processed': len(datasets_to_process),
            'total_files_processed': total_files_processed,
            'processed_datasets': [d.name for d in datasets_to_process]
        }
    }

    overall_summary_path = output_path / extraction_id / "extraction_summary.json"
    overall_summary_path.parent.mkdir(parents=True, exist_ok=True)
    with open(overall_summary_path, 'w', encoding='utf-8') as f:
        json.dump(overall_summary, f, indent=2, ensure_ascii=False)
    
    print(f"Extraction complete!")
    print(f"Total files processed: {total_files_processed}")
    print(f"Overall summary saved to: {overall_summary_path}")
    
    return 0

if __name__ == '__main__':
    exit(main())