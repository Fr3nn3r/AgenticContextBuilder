#!/usr/bin/env python3

import os
import json
import hashlib
import stat
from datetime import datetime
from pathlib import Path
import argparse
import mimetypes

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

def scan_directory(input_folder, recursive=True):
    """Scan directory and extract metadata for all files."""
    files_metadata = []
    input_path = Path(input_folder)
    
    if not input_path.exists():
        raise FileNotFoundError(f"Input folder does not exist: {input_folder}")
    
    if not input_path.is_dir():
        raise NotADirectoryError(f"Input path is not a directory: {input_folder}")
    
    # Get files based on recursive flag
    if recursive:
        file_pattern = input_path.rglob('*')
    else:
        file_pattern = input_path.iterdir()
    
    for item in file_pattern:
        metadata = extract_file_metadata(item)
        files_metadata.append(metadata)
    
    return files_metadata

def main():
    parser = argparse.ArgumentParser(
        description='Extract metadata from all files in a directory and save to JSON'
    )
    parser.add_argument(
        'input_folder',
        help='Path to the input folder to scan'
    )
    parser.add_argument(
        '-o', '--output',
        default='file_metadata.json',
        help='Output JSON file path (default: file_metadata.json)'
    )
    parser.add_argument(
        '--no-recursive',
        action='store_true',
        help='Do not scan subdirectories recursively'
    )
    parser.add_argument(
        '--pretty',
        action='store_true',
        help='Pretty-print the JSON output'
    )
    
    args = parser.parse_args()
    
    try:
        print(f"Scanning directory: {args.input_folder}")
        recursive = not args.no_recursive
        files_metadata = scan_directory(args.input_folder, recursive=recursive)
        
        # Create output structure
        output_data = {
            'scan_info': {
                'input_folder': str(Path(args.input_folder).absolute()),
                'scan_time': datetime.now().isoformat(),
                'recursive': recursive,
                'total_items': len(files_metadata),
                'successful_extractions': len([f for f in files_metadata if not f.get('metadata_extraction_failed', False)]),
                'failed_extractions': len([f for f in files_metadata if f.get('metadata_extraction_failed', False)])
            },
            'files': files_metadata
        }
        
        # Write to JSON file
        with open(args.output, 'w', encoding='utf-8') as f:
            if args.pretty:
                json.dump(output_data, f, indent=2, ensure_ascii=False)
            else:
                json.dump(output_data, f, ensure_ascii=False)
        
        print(f"Metadata extracted for {len(files_metadata)} items")
        print(f"Results saved to: {args.output}")
        
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0

if __name__ == '__main__':
    exit(main())