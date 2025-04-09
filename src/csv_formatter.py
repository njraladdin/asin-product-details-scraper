import csv
import os
from datetime import datetime
from typing import Dict, List, Any, Optional, Set


def flatten_json(json_data: Dict[str, Any], parent_key: str = '', separator: str = '_') -> Dict[str, Any]:
    """
    Recursively flatten a nested JSON structure into a single-level dictionary.
    
    Args:
        json_data: The nested JSON data to flatten
        parent_key: The parent key for nested elements (used in recursion)
        separator: The character to use for joining nested keys
        
    Returns:
        A flattened dictionary
    """
    items = {}
    for k, v in json_data.items():
        new_key = f"{parent_key}{separator}{k}" if parent_key else k
        
        if isinstance(v, dict):
            items.update(flatten_json(v, new_key, separator))
        elif isinstance(v, list):
            # Handle list items
            if all(isinstance(item, dict) for item in v):
                # For lists of dictionaries (like offers)
                for i, item in enumerate(v):
                    items.update(flatten_json(item, f"{new_key}_{i+1}", separator))
            else:
                # For simple lists, join the values
                for i, item in enumerate(v):
                    items[f"{new_key}_{i+1}"] = item
        else:
            items[new_key] = v
            
    return items


def format_product_data_for_csv(product_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format product data for CSV export by extracting and flattening key information.
    
    Args:
        product_data: The raw product data dictionary
        
    Returns:
        A dictionary formatted for CSV export
    """
    # Create a base CSV data dictionary with top-level fields
    csv_data = {
        'ASIN': product_data.get('asin', ''),
        'Timestamp': datetime.fromtimestamp(product_data.get('timestamp', 0)).strftime('%Y-%m-%d %H:%M:%S'),
    }
    
    # Extract product details
    product_details = product_data.get('product_details', {})
    
    # Add main section details
    main_section = product_details.get('main_product_details_section', {})
    if main_section:
        csv_data.update({
            'Title': main_section.get('product_title', ''),
            'Brand': main_section.get('brand', ''),
            'Price': main_section.get('price', ''),
            'Average_Rating': main_section.get('average_rating', ''),
            'Number_of_Ratings': main_section.get('number_of_ratings', ''),
        })
        
        # Add feature bullets
        feature_bullets = main_section.get('feature_bullets', [])
        for i, feature in enumerate(feature_bullets, 1):
            csv_data[f'Feature_{i}'] = feature
            
        # Add media images (first few only to avoid too many columns)
        media = main_section.get('media', {})
        images = media.get('images', [])
        for i, img in enumerate(images[:5], 1):  # Limit to first 5 images
            csv_data[f'Image_{i}_URL'] = img.get('url', '')
    
    # Add review histogram data
    reviews = product_details.get('reviews_histogram_section', {})
    if reviews:
        csv_data.update({
            'Review_Average_Rating': reviews.get('average_rating', ''),
            'Review_Total_Ratings': reviews.get('total_ratings', ''),
        })
        
        # Add distribution percentages
        distribution = reviews.get('distribution', {})
        for star, data in distribution.items():
            csv_data[f'Review_{star}_Star_Percentage'] = data.get('percentage', '')
            csv_data[f'Review_{star}_Star_Count'] = data.get('count', '')
    
    # Add product information section
    product_info = product_details.get('product_information_section', {})
    if product_info:
        for key, value in product_info.items():
            if isinstance(value, dict):
                # Handle nested dictionaries like Customer Reviews
                for sub_key, sub_value in value.items():
                    csv_data[f'Info_{key}_{sub_key}'] = sub_value
            else:
                csv_data[f'Info_{key}'] = value
    
    # Add offers data
    offers = product_data.get('offers_data', [])
    for i, offer in enumerate(offers[:5], 1):  # Limit to first 5 offers
        for key, value in offer.items():
            csv_data[f'Offer_{i}_{key}'] = value
            
    # Add any a-plus content
    aplus_content = product_details.get('aplus_content', [])
    for i, content in enumerate(aplus_content[:10], 1):  # Limit to first 10 items
        content_type = content.get('type', '')
        if content_type == 'heading':
            csv_data[f'APlus_{i}_heading'] = content.get('text', '')
        elif content_type == 'text':
            csv_data[f'APlus_{i}_text'] = content.get('text', '')
        elif content_type == 'image':
            csv_data[f'APlus_{i}_image_url'] = content.get('url', '')
            csv_data[f'APlus_{i}_image_alt'] = content.get('alt', '')
    
    return csv_data


def get_complete_flattened_data(product_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Creates a completely flattened version of the product data for CSV.
    This includes ALL fields from the original JSON.
    
    Args:
        product_data: The raw product data dictionary
        
    Returns:
        A completely flattened dictionary
    """
    return flatten_json(product_data)


def save_as_csv(product_data: Dict[str, Any], filename: str, use_complete_flattening: bool = False) -> Optional[Dict[str, Any]]:
    """
    Save product data to a CSV file.
    
    Args:
        product_data: The product data dictionary
        filename: Path to save the CSV file
        use_complete_flattening: Whether to use complete flattening (all fields) or selective formatting
        
    Returns:
        The CSV row data or None if an error occurred
    """
    try:
        # Choose the flattening method based on the flag
        if use_complete_flattening:
            csv_data = get_complete_flattened_data(product_data)
        else:
            csv_data = format_product_data_for_csv(product_data)
        
        # Create the directory if it doesn't exist
        os.makedirs(os.path.dirname(filename) or '.', exist_ok=True)
        
        # Write to CSV
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=csv_data.keys())
            writer.writeheader()
            writer.writerow(csv_data)
            
        return csv_data
        
    except Exception as e:
        print(f"Error saving CSV: {str(e)}")
        return None


def sort_fieldnames(fieldnames: List[str]) -> List[str]:
    """
    Sort fieldnames to ensure product details come first, followed by offers data.
    
    Args:
        fieldnames: List of field names to sort
        
    Returns:
        Sorted list of field names
    """
    # Define priority prefixes in the order we want them to appear
    priority_prefixes = [
        'asin', 'ASIN', 'timestamp', 'Timestamp',
        'product_details_main_product_details_section',
        'product_details_reviews_histogram_section',
        'product_details_product_information_section',
        'product_details_aplus_content',
        'product_details',
        'Brand', 'Title', 'Price', 'Average_Rating', 'Review'
    ]
    
    # Secondary importance fields
    secondary_prefixes = [
        'offers_data', 'Offer_'
    ]
    
    # Group fields by their importance
    priority_fields = []
    secondary_fields = []
    remaining_fields = []
    
    for field in fieldnames:
        # Check if field matches any priority prefix
        if any(field.startswith(prefix) for prefix in priority_prefixes):
            priority_fields.append(field)
        # Check if field matches any secondary prefix
        elif any(field.startswith(prefix) for prefix in secondary_prefixes):
            secondary_fields.append(field)
        # If no match, add to remaining fields
        else:
            remaining_fields.append(field)
    
    # Sort within each group
    priority_fields.sort()
    secondary_fields.sort()
    remaining_fields.sort()
    
    # Combine all groups in order of priority
    return priority_fields + remaining_fields + secondary_fields


def save_combined_csv(csv_data_list: List[Dict[str, Any]], filename: str) -> bool:
    """
    Save multiple products' data to a single CSV file.
    
    Args:
        csv_data_list: List of CSV data dictionaries
        filename: Path to save the combined CSV file
        
    Returns:
        True if successful, False otherwise
    """
    if not csv_data_list:
        return False
        
    try:
        # Get all possible field names from all products
        all_fields: Set[str] = set()
        for data in csv_data_list:
            all_fields.update(data.keys())
            
        # Sort fieldnames to put product details first, then offers
        fieldnames = sort_fieldnames(list(all_fields))
        
        # Create the directory if it doesn't exist
        os.makedirs(os.path.dirname(filename) or '.', exist_ok=True)
        
        # Write all products to a single CSV
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(csv_data_list)
            
        return True
    except Exception as e:
        print(f"Error saving combined CSV: {str(e)}")
        return False 