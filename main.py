#!/usr/bin/env python3
"""
Picture Sorter - Rename image files based on their metadata timestamps.
"""

import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, Set

import click
from PIL import Image
from PIL.ExifTags import TAGS


class PicSorter:
    """Main class for picture sorting functionality."""
    
    SUPPORTED_EXTENSIONS: Set[str] = {
        '.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp', '.gif', '.webp'
    }
    
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.processed_count = 0
        self.error_count = 0
    
    def find_image_files(self, folder_path: Path) -> list[Path]:
        """Recursively find all image files in the given folder."""
        image_files = []
        
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                file_path = Path(root) / file
                if file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS:
                    image_files.append(file_path)
        
        return image_files
    
    def extract_date_taken(self, image_path: Path) -> tuple[Optional[datetime], bool]:
        """Extract the date taken from image metadata.
        
        Returns:
            tuple: (datetime, is_fallback) where is_fallback indicates if file mtime was used
        """
        try:
            with Image.open(image_path) as img:
                exif = img.getexif()
                
                if exif:
                    for tag_id, value in exif.items():
                        tag = TAGS.get(tag_id, tag_id)
                        if tag in ['DateTime', 'DateTimeOriginal', 'DateTimeDigitized']:
                            try:
                                return datetime.strptime(value, '%Y:%m:%d %H:%M:%S'), False
                            except ValueError:
                                continue
                
                # If no EXIF date found, use file modification time as fallback
                mtime = os.path.getmtime(image_path)
                return datetime.fromtimestamp(mtime), True
                
        except Exception as e:
            click.echo(f"Error reading metadata from {image_path}: {e}", err=True)
            return None, False
    
    def generate_new_filename(self, original_path: Path, date_taken: datetime, is_fallback: bool) -> Path:
        """Generate new filename based on the yyyyMMddHHmmSS pattern."""
        date_str = date_taken.strftime('%Y%m%d%H%M%S')
        extension = original_path.suffix.lower()
        
        # Determine target directory
        if is_fallback:
            no_exif_dir = original_path.parent / "no-exif"
            no_exif_dir.mkdir(exist_ok=True)
            target_dir = no_exif_dir
        else:
            target_dir = original_path.parent
        
        new_filename = f"{date_str}{extension}"
        new_path = target_dir / new_filename
        
        # Handle filename conflicts by adding a counter
        counter = 1
        while new_path.exists() and new_path != original_path:
            new_filename = f"{date_str}_{counter:02d}{extension}"
            new_path = target_dir / new_filename
            counter += 1
        
        return new_path
    
    def rename_file(self, original_path: Path, new_path: Path) -> bool:
        """Rename the file if the new name is different."""
        if original_path == new_path:
            return True
        
        try:
            if self.dry_run:
                click.echo(f"Would rename: {original_path.name} -> {new_path.name}")
            else:
                original_path.rename(new_path)
                click.echo(f"Renamed: {original_path.name} -> {new_path.name}")
            return True
        except Exception as e:
            click.echo(f"Error renaming {original_path} to {new_path}: {e}", err=True)
            return False
    
    def process_folder(self, folder_path: Path) -> None:
        """Process all images in the folder."""
        if not folder_path.exists():
            click.echo(f"Error: Folder '{folder_path}' does not exist.", err=True)
            sys.exit(1)
        
        if not folder_path.is_dir():
            click.echo(f"Error: '{folder_path}' is not a directory.", err=True)
            sys.exit(1)
        
        image_files = self.find_image_files(folder_path)
        
        if not image_files:
            click.echo("No image files found in the specified folder.")
            return
        
        click.echo(f"Found {len(image_files)} image files.")
        
        if self.dry_run:
            click.echo("DRY RUN MODE - No files will be actually renamed.\n")
        
        for image_path in image_files:
            date_taken, is_fallback = self.extract_date_taken(image_path)
            
            if date_taken is None:
                click.echo(f"Skipping {image_path.name}: Could not extract date", err=True)
                self.error_count += 1
                continue
            
            new_path = self.generate_new_filename(image_path, date_taken, is_fallback)
            
            if self.rename_file(image_path, new_path):
                self.processed_count += 1
                if is_fallback:
                    click.echo(f"  (moved to no-exif folder - no EXIF data found)")
            else:
                self.error_count += 1
        
        click.echo(f"\nProcessing complete!")
        click.echo(f"Successfully processed: {self.processed_count} files")
        if self.error_count > 0:
            click.echo(f"Errors encountered: {self.error_count} files")


@click.command()
@click.argument('folder_path', type=click.Path(exists=True, path_type=Path))
@click.option('--dry-run', is_flag=True, help='Show what would be renamed without actually renaming files')
def main(folder_path: Path, dry_run: bool):
    """
    Rename image files based on their metadata timestamps.
    
    FOLDER_PATH: Path to the folder containing images to be renamed.
    
    The tool will recursively search for image files and rename them using the 
    pattern yyyyMMddHHmmSS based on the date/time the photo was taken.
    """
    sorter = PicSorter(dry_run=dry_run)
    sorter.process_folder(folder_path)


if __name__ == "__main__":
    main()
