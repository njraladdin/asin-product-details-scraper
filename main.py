import argparse
import json
import os
import csv
import sys
from datetime import datetime
from colorama import init, Fore, Style
from src.amazon_scraper import AmazonScraper
from src.csv_formatter import save_as_csv, save_combined_csv, get_complete_flattened_data


# Initialize colorama for colored console output
init(autoreset=True)

def process_asin(scraper, asin, combined_csv_data=None):
    """Process a single ASIN and save its data
    
    Args:
        scraper: The AmazonScraper instance
        asin: The ASIN to process
        combined_csv_data: List to append CSV data for multiple products
        
    Returns:
        bool: Success or failure
        dict: CSV row data 
    """
    try:
        # Get product data
        result = scraper.get_product_data(asin)
        if not result:
            print(f"{Fore.RED}[ERROR] Failed to get data for ASIN: {asin}{Style.RESET_ALL}")
            return False, None

        # Create output directory if it doesn't exist
        os.makedirs('output', exist_ok=True)

        # Generate timestamp for filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save as JSON
        json_filename = f'output/product_{asin}_{timestamp}.json'
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"{Fore.GREEN}[SUCCESS] Saved product data to {json_filename}{Style.RESET_ALL}")
        
        # Prepare CSV data for the combined CSV file
        csv_data = get_complete_flattened_data(result)
        
        return True, csv_data

    except Exception as e:
        print(f"{Fore.RED}[ERROR] Failed to process ASIN {asin}: {str(e)}{Style.RESET_ALL}")
        return False, None

def main():
    # Set up argument parser with simple help messages
    parser = argparse.ArgumentParser(
        description='Amazon Product Data Scraper',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  1. Get data by entering ASINs directly:
     python main.py B09X7CRKRZ B07CRG7BBH

  2. Get data from a file (TXT or CSV):
     python main.py --file asins.txt
     python main.py --file products.csv
"""
    )

    # Add arguments
    parser.add_argument('asins', nargs='*')
    parser.add_argument('--file')

    # Parse arguments
    args = parser.parse_args()

    # Check if any ASINs were provided
    if not args.asins and not args.file:
        parser.print_help()
        print(f"\n{Fore.RED}[ERROR] Please provide at least one ASIN or a file containing ASINs{Style.RESET_ALL}")
        return

    # Collect all ASINs
    all_asins = set(args.asins)  # Start with command line ASINs

    # Add ASINs from file if provided
    if args.file:
        try:
            file_ext = os.path.splitext(args.file)[1].lower()
            
            if file_ext == '.csv':
                # Handle CSV file
                with open(args.file, 'r', newline='') as f:
                    csv_reader = csv.DictReader(f)
                    if 'asin' not in csv_reader.fieldnames:
                        print(f"{Fore.RED}[ERROR] CSV file must have an 'asin' column{Style.RESET_ALL}")
                        return
                    file_asins = [row['asin'].strip() for row in csv_reader if row['asin'].strip()]
                    all_asins.update(file_asins)
            else:
                # Handle text file (one ASIN per line)
                with open(args.file, 'r') as f:
                    file_asins = [line.strip() for line in f if line.strip()]
                    all_asins.update(file_asins)
                    
            print(f"{Fore.GREEN}[INFO] Loaded {len(file_asins)} ASINs from file: {args.file}{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.RED}[ERROR] Failed to read ASINs from file: {str(e)}{Style.RESET_ALL}")
            return

    # Remove any empty ASINs
    all_asins = [asin for asin in all_asins if asin]

    if not all_asins:
        print(f"{Fore.RED}[ERROR] No valid ASINs found{Style.RESET_ALL}")
        return

    print(f"\n{Fore.CYAN}Processing {len(all_asins)} ASINs...{Style.RESET_ALL}")

    # Initialize scraper
    scraper = AmazonScraper()

    # Prepare for CSV data collection
    combined_csv_data = []

    # Process each ASIN
    success_count = 0
    for asin in all_asins:
        print(f"\n{Fore.CYAN}Processing ASIN: {asin}{Style.RESET_ALL}")
        success, csv_data = process_asin(scraper, asin, combined_csv_data)
        if success:
            success_count += 1
            if csv_data:
                combined_csv_data.append(csv_data)

    # Save consolidated CSV with all products
    if combined_csv_data:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        combined_filename = f'output/all_products_{timestamp}.csv'
        if save_combined_csv(combined_csv_data, combined_filename):
            print(f"{Fore.GREEN}[SUCCESS] Saved all product data to {combined_filename}{Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}[ERROR] Failed to save consolidated CSV file{Style.RESET_ALL}")

    # Print summary
    print(f"\n{Fore.CYAN}=== Summary ==={Style.RESET_ALL}")
    print(f"Total ASINs processed: {len(all_asins)}")
    print(f"Successfully saved: {success_count}")
    print(f"Failed: {len(all_asins) - success_count}")
    print(f"Output files are in the 'output' folder")

if __name__ == "__main__":
    main() 