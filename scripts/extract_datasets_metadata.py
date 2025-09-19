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

def process_dataset_folder(dataset_path, output_base_path):
    """Process a single dataset folder and create individual metadata files."""
    dataset_name = Path(dataset_path).name
    output_dataset_path = Path(output_base_path) / dataset_name
    
    # Create output directory structure
    output_dataset_path.mkdir(parents=True, exist_ok=True)
    
    processed_files = []
    
    # Process all files in the dataset folder
    for item in Path(dataset_path).iterdir():
        if item.is_file():
            print(f"  Processing file: {item.name}")
            
            # Extract metadata
            metadata = extract_file_metadata(item)
            
            # Add processing information
            processing_info = {
                'extraction_time': datetime.now().isoformat(),
                'source_dataset': dataset_name,
                'output_path': str(output_dataset_path),
            }
            
            # Combine metadata with processing info
            file_metadata = {
                'processing_info': processing_info,
                'file_metadata': metadata
            }
            
            # Create individual metadata file
            metadata_filename = f"{item.stem}_metadata.json"
            metadata_file_path = output_dataset_path / metadata_filename
            
            # Write metadata to individual file
            with open(metadata_file_path, 'w', encoding='utf-8') as f:
                json.dump(file_metadata, f, indent=2, ensure_ascii=False)
            
            processed_files.append({
                'original_file': str(item),
                'metadata_file': str(metadata_file_path),
                'file_name': item.name,
                'metadata_filename': metadata_filename
            })
    
    # Create a summary file for the dataset
    dataset_summary = {
        'dataset_info': {
            'dataset_name': dataset_name,
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
    
    args = parser.parse_args()
    
    input_path = Path(args.input_folder)
    output_path = Path(args.output_folder)
    
    if not input_path.exists():
        print(f"Error: Input folder does not exist: {input_path}")
        return 1
    
    if not input_path.is_dir():
        print(f"Error: Input path is not a directory: {input_path}")
        return 1
    
    # Create output directory
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Get list of dataset folders (directories only)
    dataset_folders = [d for d in input_path.iterdir() if d.is_dir()]
    dataset_folders.sort()  # Sort for consistent ordering
    
    if not dataset_folders:
        print(f"No dataset folders found in {input_path}")
        return 1
    
    # Process first N datasets
    datasets_to_process = dataset_folders[:args.num_datasets]
    
    print(f"Processing {len(datasets_to_process)} datasets from {input_path}")
    print(f"Output will be saved to: {output_path}")
    print()
    
    total_files_processed = 0
    
    for i, dataset_folder in enumerate(datasets_to_process, 1):
        print(f"[{i}/{len(datasets_to_process)}] Processing dataset: {dataset_folder.name}")
        
        try:
            files_processed = process_dataset_folder(dataset_folder, output_path)
            total_files_processed += files_processed
            print(f"  [OK] Processed {files_processed} files")
        except Exception as e:
            print(f"  [ERROR] Error processing dataset {dataset_folder.name}: {e}")
        
        print()
    
    # Create overall summary
    overall_summary = {
        'extraction_summary': {
            'input_folder': str(input_path),
            'output_folder': str(output_path),
            'processing_time': datetime.now().isoformat(),
            'datasets_requested': args.num_datasets,
            'datasets_processed': len(datasets_to_process),
            'total_files_processed': total_files_processed,
            'processed_datasets': [d.name for d in datasets_to_process]
        }
    }
    
    overall_summary_path = output_path / "extraction_summary.json"
    with open(overall_summary_path, 'w', encoding='utf-8') as f:
        json.dump(overall_summary, f, indent=2, ensure_ascii=False)
    
    print(f"Extraction complete!")
    print(f"Total files processed: {total_files_processed}")
    print(f"Overall summary saved to: {overall_summary_path}")
    
    return 0

if __name__ == '__main__':
    exit(main())