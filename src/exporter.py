import os
import json
from datetime import datetime
from colorama import Fore, Style
from typing import List, Dict, Any, Tuple

from .csv_formatter import save_combined_csv, get_complete_flattened_data


def export_product_data(result: Dict[str, Any], asin: str) -> Tuple[bool, Dict[str, Any]]:
    """Export product data to JSON and prepare CSV data
    
    Args:
        result: The product data to export
        asin: The ASIN of the product
        
    Returns:
        Tuple containing:
        - bool: Success or failure
        - dict: CSV row data for combined CSV export
    """
    try:
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
        print(f"{Fore.RED}[ERROR] Failed to export data for ASIN {asin}: {str(e)}{Style.RESET_ALL}")
        return False, None


def export_combined_products(combined_csv_data: List[Dict[str, Any]]) -> bool:
    """Export combined product data to a single CSV file
    
    Args:
        combined_csv_data: List of CSV data for each product
        
    Returns:
        bool: Success or failure
    """
    if not combined_csv_data:
        return False
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    combined_filename = f'output/all_products_{timestamp}.csv'
    
    if save_combined_csv(combined_csv_data, combined_filename):
        print(f"{Fore.GREEN}[SUCCESS] Saved all product data to {combined_filename}{Style.RESET_ALL}")
        return True
    else:
        print(f"{Fore.RED}[ERROR] Failed to save consolidated CSV file{Style.RESET_ALL}")
        return False


def print_summary(total_count: int, success_count: int) -> None:
    """Print a summary of the export process
    
    Args:
        total_count: Total number of ASINs processed
        success_count: Number of successfully processed ASINs
    """
    print(f"\n{Fore.CYAN}=== Summary ==={Style.RESET_ALL}")
    print(f"Total ASINs processed: {total_count}")
    print(f"Successfully saved: {success_count}")
    print(f"Failed: {total_count - success_count}")
    print(f"Output files are in the 'output' folder") 