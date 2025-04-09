import argparse
import csv
import os
import sys
from colorama import init, Fore, Style
from src.amazon_scraper import AmazonScraper
from src.exporter import export_product_data, export_combined_products, print_summary


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
    """
    try:
        # Get product data
        result = scraper.get_product_data(asin)
        if not result:
            print(f"{Fore.RED}[ERROR] Failed to get data for ASIN: {asin}{Style.RESET_ALL}")
            return False

        # Export product data to files and get CSV data
        success, csv_data = export_product_data(result, asin)
        
        # If export successful and we have CSV data, add to combined data
        if success and csv_data and combined_csv_data is not None:
            combined_csv_data.append(csv_data)
            
        return success

    except Exception as e:
        print(f"{Fore.RED}[ERROR] Failed to process ASIN {asin}: {str(e)}{Style.RESET_ALL}")
        return False

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
        if process_asin(scraper, asin, combined_csv_data):
            success_count += 1

    # Export combined product data to CSV
    if combined_csv_data:
        export_combined_products(combined_csv_data)

    # Print summary of processing
    print_summary(len(all_asins), success_count)

if __name__ == "__main__":
    main() 