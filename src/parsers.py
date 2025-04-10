from lxml import html
import json
from datetime import datetime, timedelta
import re
import os
import unicodedata

def clean_unicode_control_chars(text):
    """
    Removes Unicode control characters and other problematic invisible characters.
    Specifically targets characters like U+200E (Left-to-Right Mark) that might
    appear as mojibake in the output.
    
    Args:
        text (str): The text to clean
        
    Returns:
        str: The cleaned text with control characters removed
    """
    if not text:
        return text
        
    # Remove Left-to-Right Mark and Right-to-Left Mark
    text = text.replace('\u200E', '').replace('\u200F', '')
    
    # Remove other Unicode control and formatting characters (category "C" and "Z")
    # But keep normal whitespace
    clean_text = ''.join(ch for ch in text if not unicodedata.category(ch).startswith(('C', 'Z')) 
                         or ch in (' ', '\t', '\n', '\r'))
    
    return clean_text

def parse_offers(html_text):
    """
    Parses HTML containing Amazon offers and returns a JSON object of the offers data.
    
    Returns:
        tuple: (offers_json, has_prime_filter) where:
            - offers_json is the JSON string of parsed offers
            - has_prime_filter is a boolean indicating if Prime filter is available
    """
    # Ensure debug directory exists
    os.makedirs('output_debug', exist_ok=True)
    
    # Save HTML content to debug folder
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_path = f'output_debug/offers_{timestamp}.html'
    
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_text)
    except Exception as e:
        print(f"Warning: Could not save HTML to {output_path}: {str(e)}")
    
    tree = html.fromstring(html_text)
    offers = []

    # Check if Prime filter exists
    filter_list = tree.xpath('//div[@id="aod-filter-list"]')
    has_prime_filter = False
    if filter_list is not None and len(filter_list) > 0:
        # Look for Prime icon in the filter list
        prime_checkbox = filter_list[0].xpath('.//i[contains(@class, "a-icon-prime")]')
        has_prime_filter = len(prime_checkbox) > 0

    # Find the pinned offer first (if present)
    pinned_offer = tree.xpath('//div[@id="aod-pinned-offer"]')
    if pinned_offer:
        offers.append(extract_offer_data(pinned_offer[0], True))

    # Find all offer divs
    offer_divs = tree.xpath('//div[@id="aod-offer"]')
    for offer_div in offer_divs:
        offers.append(extract_offer_data(offer_div, False))

    return json.dumps(offers, indent=2), has_prime_filter

def parse_delivery_days(delivery_estimate):
    """Convert delivery estimate text to earliest and latest days"""
    if not delivery_estimate:
        return None, None, None
        
    # Add debug logging
    print(f"Parsing delivery estimate: {delivery_estimate}")
    
    # Handle overnight delivery, today, and tomorrow with time ranges
    delivery_estimate_lower = delivery_estimate.lower()
    
    # Extract time range if present (e.g., "7 AM - 11 AM")
    time_range = None
    time_match = re.search(r'(\d+(?::\d+)?\s*(?:AM|PM)\s*-\s*\d+(?::\d+)?\s*(?:AM|PM))', delivery_estimate, re.IGNORECASE)
    if time_match:
        time_range = time_match.group(1)
    
    if 'overnight' in delivery_estimate_lower:
        return 0, 0, time_range
    elif 'today' in delivery_estimate_lower:
        return 0, 0, time_range
    elif 'tomorrow' in delivery_estimate_lower:
        return 1, 1, time_range
    
    # Strip time component from today
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    print(f"Today's date: {today}")
    
    months = {
        'January': 1, 'February': 2, 'March': 3, 'April': 4,
        'May': 5, 'June': 6, 'July': 7, 'August': 8,
        'September': 9, 'October': 10, 'November': 11, 'December': 12
    }
    
    # First find which months are mentioned in the estimate
    mentioned_months = [month for month in months if month in delivery_estimate]
    
    if mentioned_months:
        # Extract date range like "February 10 - 13" or "February 24 - March 11"
        dates = re.findall(r'\d+', delivery_estimate)
        if len(dates) >= 2:  # We have a range
            earliest_day = int(dates[0])
            latest_day = int(dates[1])
            
            # If there are two different months mentioned, use them respectively
            if len(mentioned_months) >= 2:
                earliest_month = months[mentioned_months[0]]
                latest_month = months[mentioned_months[1]]
            else:
                earliest_month = latest_month = months[mentioned_months[0]]
            
            year = today.year
            
            # Handle year transition for each date separately
            earliest_year = year
            if earliest_month < today.month:
                earliest_year += 1
                
            latest_year = year
            if latest_month < today.month:
                latest_year += 1
            
            earliest_date = datetime(earliest_year, earliest_month, earliest_day)
            latest_date = datetime(latest_year, latest_month, latest_day)
            
            print(f"Calculated dates - earliest: {earliest_date}, latest: {latest_date}")
            
            earliest_days = (earliest_date - today).days
            latest_days = (latest_date - today).days
            
            print(f"Days calculation - earliest_days: {earliest_days}, latest_days: {latest_days}")
            
            return earliest_days, latest_days, time_range
            
        elif len(dates) == 1:  # Single date
            day = int(dates[0])
            month_num = months[mentioned_months[0]]
            year = today.year
            if month_num < today.month:
                year += 1
            
            delivery_date = datetime(year, month_num, day)
            
            days_until = (delivery_date - today).days
            
            return days_until, days_until, time_range
    
    return None, None, None

def extract_offer_data(offer_div, is_pinned):
    """
    Extracts offer data from a single offer div using lxml.
    """
    
    offer_data = {
        'seller_id': None,
        'buy_box_winner': is_pinned,
        'prime': False,
        'earliest_days': None,
        'latest_days': None,
        'delivery_time_range': None,  # New field for time range
    }

    # Check for Prime badge in the offer
    prime_badge = offer_div.xpath('.//i[contains(@class, "a-icon-prime")]')
    if prime_badge:
        offer_data['prime'] = True

    # Price components
    price_span = offer_div.xpath('.//span[contains(@class, "a-price")]')
    if price_span:
        whole = price_span[0].xpath('.//span[@class="a-price-whole"]/text()')
        fraction = price_span[0].xpath('.//span[@class="a-price-fraction"]/text()')
        if whole and fraction:
            # Add decimal point between whole and fraction
            price_str = whole[0].strip() + '.' + fraction[0].strip()
            price_str = re.sub(r'[^\d.]', '', price_str)
            offer_data['price'] = float(price_str)
            offer_data['total_price'] = offer_data['price']

    # Delivery information
    delivery_promise = offer_div.xpath('.//div[contains(@class, "aod-delivery-promise")]')
    if delivery_promise:
        # First check for fastest delivery option
        fastest_delivery = delivery_promise[0].xpath('.//span[@data-csa-c-content-id="DEXUnifiedCXSDM"]')
        primary_delivery = delivery_promise[0].xpath('.//span[@data-csa-c-content-id="DEXUnifiedCXPDM"]')
        
        delivery_element = None
        if fastest_delivery:
            delivery_element = fastest_delivery[0]
        elif primary_delivery:
            delivery_element = primary_delivery[0]
            
        if delivery_element is not None:
            shipping_cost = delivery_element.get('data-csa-c-delivery-price')
            if shipping_cost == 'FREE':
                offer_data['shipping_cost'] = 0.0
            else:
                shipping_cost = re.sub(r'[^\d.]', '', shipping_cost)
                offer_data['shipping_cost'] = float(shipping_cost) if shipping_cost else 0.0
            
            offer_data['total_price'] = offer_data['price'] + offer_data['shipping_cost']

            delivery_time = delivery_element.xpath('.//span[@class="a-text-bold"]')
            if delivery_time:
                delivery_text = ' '.join([text.strip() for text in delivery_time[0].xpath('.//text()')])
                earliest, latest, time_range = parse_delivery_days(delivery_text)
                
                # Format delivery estimate with time range if available
                if time_range:
                    if 'overnight' in delivery_text.lower():
                        offer_data['delivery_estimate'] = f"Overnight {time_range}"
                    elif 'today' in delivery_text.lower():
                        offer_data['delivery_estimate'] = f"Today {time_range}"
                    else:
                        offer_data['delivery_estimate'] = delivery_text
                else:
                    offer_data['delivery_estimate'] = delivery_text
                
                offer_data['earliest_days'] = earliest
                offer_data['latest_days'] = latest
                offer_data['delivery_time_range'] = time_range

    # Seller information
    sold_by_div = offer_div.xpath('.//div[@id="aod-offer-soldBy"]')
    if sold_by_div:
        # Try to find seller link (third party sellers) or span (Amazon)
        seller_element = (
            sold_by_div[0].xpath('.//a[@class="a-size-small a-link-normal"]') or 
            sold_by_div[0].xpath('.//span[@class="a-size-small a-color-base"]')
        )
        
        if seller_element:
            offer_data['seller_name'] = seller_element[0].text.strip()
            seller_url = seller_element[0].get('href', '1')  # Use '1' as URL for Amazon.com
            offer_data['seller_id'] = extract_seller_id(seller_url)

    return offer_data

def extract_seller_id(seller_url):
    """Extract seller ID from seller URL"""
    if not seller_url:
        return None
    
    # # Special case for Amazon's URL which is just "1"
    # if seller_url == "1":
    #     return "ATVPDKIKX0DER"  # Amazon.com's seller ID
    
    # Look for seller= parameter in URL
    if 'seller=' in seller_url:
        return seller_url.split('seller=')[1].split('&')[0]
    return None


def parse_product_details(html_text):
    """
    Parses ALL product details from the main product HTML section.

    Args:
        html_text: The HTML content of the product page.

    Returns:
        A dictionary containing the parsed product details. Returns an empty
        dictionary if the main product details section is not found.
    """
    try:
        print("DEBUG: Starting parse_product_details")
        tree = html.fromstring(html_text)
        product_details = {}
        main_product_details_section = {}

        # Find the main product details section
        print("DEBUG: Searching for centerCol")
        center_col = tree.xpath('//div[@id="centerCol"]')
        if not center_col:
            print("WARNING: centerCol not found.") # Added warning
            return {}

        center_col = center_col[0]
        print("DEBUG: centerCol found successfully")

        # --- Basic Details ---
        print("DEBUG: Parsing basic details")
        try:
            title_element = center_col.xpath('.//span[@id="productTitle"]')
            if title_element:
                title_text = title_element[0].text_content().strip() # Use text_content() for robustness
                # Clean the title text of special Unicode characters
                title_text = clean_unicode_control_chars(title_text)
                main_product_details_section['product_title'] = title_text
                print(f"DEBUG: Found product title: {main_product_details_section['product_title'][:30]}...")
        except Exception as e:
            print(f"ERROR in product title extraction: {str(e)}")

        try:
            brand_element = center_col.xpath('.//a[@id="bylineInfo"]')
            if brand_element:
                brand_text = brand_element[0].text_content().strip() # Use text_content()
                print(f"DEBUG: Raw brand text: {brand_text}")
                # More robust brand extraction
                if brand_text.startswith(("Visit the ", "Brand: ")):
                    brand_text = brand_text.split(" ", 1)[1] # Take text after first space
                    if brand_text.endswith(" Store"):
                        brand_text = brand_text[:-len(" Store")]
                elif brand_text.startswith("Shop "): # Handle cases like "Shop LG"
                    brand_text = brand_text.split(" ", 1)[1]
                # Clean Unicode control characters from brand text
                brand_text = clean_unicode_control_chars(brand_text)
                main_product_details_section['brand'] = brand_text
                print(f"DEBUG: Extracted brand: {brand_text}")
        except Exception as e:
            print(f"ERROR in brand extraction: {str(e)}")

        try:
            rating_element = center_col.xpath('.//span[@id="acrPopover"]')
            if rating_element:
                rating_title = rating_element[0].get('title')
                print(f"DEBUG: Rating title: {rating_title}")
                if rating_title:
                    try:
                        main_product_details_section['average_rating'] = float(rating_title.split()[0])
                        print(f"DEBUG: Extracted rating: {main_product_details_section['average_rating']}")
                    except (ValueError, IndexError) as e:
                        print(f"WARNING: Could not parse rating from title: {rating_title}. Error: {str(e)}")
        except Exception as e:
            print(f"ERROR in rating extraction: {str(e)}")

        # Continue with more sections...
        print("DEBUG: Completed basic details extraction")

        # --- "About this item" Bullets ---
        print("DEBUG: Parsing feature bullets")
        try:
            about_item_bullets = []
            # More specific selector to avoid grabbing nested span text unintentionally
            bullet_elements = center_col.xpath('.//div[@id="feature-bullets"]//ul/li/span[contains(@class, "a-list-item")]')
            print(f"DEBUG: Found {len(bullet_elements)} bullet elements")
            for li_span in bullet_elements:
                # Get all text directly under the span, ignoring children like <a>
                bullet_text = ''.join(li_span.xpath('./text()')).strip()
                if bullet_text:
                    # Clean Unicode control characters from bullet text
                    bullet_text = clean_unicode_control_chars(bullet_text)
                    about_item_bullets.append(bullet_text)
            if about_item_bullets:
                main_product_details_section['feature_bullets'] = about_item_bullets
                print(f"DEBUG: Extracted {len(about_item_bullets)} feature bullets")
        except Exception as e:
            print(f"ERROR in feature bullets extraction: {str(e)}")

        # --- Available Options/Variations ---
        print("DEBUG: Parsing available options/variations")
        try:
            options = []
            # Adjusted selector for variations (might need further tuning based on page structure)
            option_elements = tree.xpath('//div[contains(@id, "twister-")]//li[contains(@class, "swatch-list-item")]')
            print(f"DEBUG: Found {len(option_elements)} option elements")
            for option in option_elements:
                option_data = {}
                # Check for data-asin first, fallback to other attributes if needed
                option_data['asin'] = option.get('data-asin') or option.get('id', '').replace('size_name_', '').replace('color_name_', '')

                # Get the size/capacity/color etc. (handle different variation types)
                label_element = option.xpath('.//span[contains(@class, "a-size-base")]/text()') # More generic label
                if label_element:
                     label_text = label_element[0].strip()
                     # Clean Unicode control characters from label text
                     label_text = clean_unicode_control_chars(label_text)
                     option_data['label'] = label_text
                else: # Fallback for image swatches alt text
                     img_alt = option.xpath('.//img/@alt')
                     if img_alt:
                         alt_text = img_alt[0].strip()
                         # Clean Unicode control characters from alt text
                         alt_text = clean_unicode_control_chars(alt_text)
                         option_data['label'] = alt_text

                # Get the price (use text_content() for robustness)
                price_element = option.xpath('.//span[contains(@class, "a-price")]/span[@aria-hidden="true"]')
                if price_element:
                    price_text = price_element[0].text_content().strip()
                    price_str = re.sub(r'[^\d.]', '', price_text) # Remove currency symbols etc.
                    try:
                        option_data['price'] = float(price_str) if price_str else None
                    except ValueError:
                        option_data['price'] = None

                # Get availability (use text_content() for robustness)
                availability = option.xpath('.//span[contains(@id, "availability")]/text()') # More generic availability id
                if availability:
                    option_data['availability'] = availability[0].strip()

                # Check if this is the selected option
                # Check parent span or the li itself for selected class
                selected_class_check = option.xpath('.//span[contains(@class, "a-button-selected")] | .[@class="a-declarative"]//span[contains(@class, "a-button-selected")] | self::*[contains(@class, "selected")]')
                option_data['selected'] = bool(selected_class_check)

                # Only add if we have an ASIN and a label
                if option_data.get('asin') and option_data.get('label'):
                    options.append(option_data)

            if options:
                main_product_details_section['available_options'] = options
                print(f"DEBUG: Extracted {len(options)} available options")
        except Exception as e:
            print(f"ERROR in options extraction: {str(e)}")

        # --- Product Media ---
        print("DEBUG: Parsing product media")
        try:
            media = {
                'images': [],
                'videos': []
            }
            # Find the ImageBlockATF script that contains the image data
            image_script = tree.xpath('//script[contains(text(), "ImageBlockATF")]/text()')
            print(f"DEBUG: Found {len(image_script)} image scripts")
            if image_script:
                script_text = image_script[0]
                try:
                    # More robust regex to find the initial image data array
                    match = re.search(r"'colorImages':\s*{\s*'initial':\s*(\[.*?\])\s*}", script_text, re.DOTALL)
                    if match:
                        print("DEBUG: Found colorImages match in script")
                        image_data_str = match.group(1)
                        # Basic cleaning for JSON parsing
                        image_data_str = image_data_str.replace("'", '"')
                        # Handle potential invalid JSON like trailing commas (less robust, but common)
                        image_data_str = re.sub(r',\s*\]', ']', image_data_str)
                        image_data_str = re.sub(r',\s*}', '}', image_data_str)
                        
                        print(f"DEBUG: Parsing JSON string for images (first 100 chars): {image_data_str[:100]}...")
                        images = json.loads(image_data_str)
                        print(f"DEBUG: Successfully parsed {len(images)} images from JSON")
                        for img in images:
                            # Prioritize hiRes, fallback to large
                            img_url = img.get('hiRes') or img.get('large')
                            if img_url:
                                image_data = {
                                    'url': img_url,
                                    'high_res': bool(img.get('hiRes')), # Indicate if hiRes was available
                                    'thumbnail': img.get('thumb'),
                                    'variant': img.get('variant'),
                                    'large': img.get('large') # Keep large even if hiRes is primary
                                }
                                media['images'].append(image_data)
                    else:
                        print("WARNING: 'colorImages' array not found in ImageBlockATF script.")
                except (json.JSONDecodeError, KeyError, TypeError) as e:
                    print(f"ERROR: Could not parse image data from script: {str(e)}")
                    print(f"ERROR: JSON parsing error location: {getattr(e, 'pos', 'unknown')}")
                    # Add more context about the JSON that failed parsing
                    if 'match' in locals() and match:
                        print(f"Problematic JSON string (first 200 chars): {match.group(1)[:200]}...")
                    elif 'image_data_str' in locals():
                        print(f"Problematic JSON string (first 200 chars): {image_data_str[:200]}...")
        except Exception as e:
            print(f"ERROR in media extraction: {str(e)}")

        # Extract product videos (improved selector)
        print("DEBUG: Parsing product videos")
        try:
            video_elements = tree.xpath('//div[contains(@class, "vdp-video-card")] | //div[contains(@class, "vse-player-container")]')
            for video_container in video_elements:
                # Try extracting from data attributes first (common in newer layouts)
                video_url = video_container.xpath('.//video/@src | .//@data-video-url')
                thumb_url = video_container.xpath('.//video/@poster | .//img/@src | .//@data-thumbnail-url')
                title_elem = video_container.xpath('.//div[contains(@class, "title")]/text() | .//span[contains(@class, "title")]/text()')

                # Fallback to script data state if direct attributes fail
                if not video_url:
                    video_state_script = video_container.xpath('.//script[@type="a-state"]/text()')
                    if video_state_script:
                         try:
                             video_data = json.loads(video_state_script[0])
                             video_url = [video_data.get('videoUrl')] # Wrap in list for consistency
                             thumb_url = [video_data.get('imageUrl')]
                             title_elem = [video_data.get('title')]
                         except (json.JSONDecodeError, KeyError):
                             pass # Ignore script parsing errors silently

                if video_url and video_url[0]:
                    title_text = title_elem[0].strip() if title_elem and title_elem[0] else None
                    if title_text:
                        title_text = clean_unicode_control_chars(title_text)
                    media_item = {
                        'url': video_url[0],
                        'thumbnail': thumb_url[0] if thumb_url else None,
                        'title': title_text
                    }
                    media['videos'].append(media_item)
        except Exception as e:
            print(f"ERROR in video extraction: {str(e)}")

        if media['images'] or media['videos']:
            main_product_details_section['media'] = media
            print(f"DEBUG: Extracted {len(media['images'])} images and {len(media['videos'])} videos")

        # Add the main section details to the product_details dictionary
        print("DEBUG: Finalizing product details")
        if main_product_details_section:
            product_details['main_product_details_section'] = main_product_details_section

        # --- Review Histogram Section ---
        print("DEBUG: Parsing reviews histogram")
        try:
            try:
                histogram_xpath = '//div[@id="reviewsMedley"] | //div[@id="cm_cr_dp_d_rating_histogram"]'
                review_histogram = tree.xpath(histogram_xpath)
                print(f"DEBUG: Found {len(review_histogram)} review histogram sections")
            except Exception as xpath_error:
                print(f"ERROR: Invalid XPath expression in review histogram: {str(xpath_error)}")
                review_histogram = []
                
            if review_histogram:
                reviews_data = {
                    'average_rating': None,
                    'total_ratings': None,
                    'distribution': {}
                }
                hist_container = review_histogram[0] # Work within the found container

                # Get average rating (look for text like '4.0 out of 5 stars')
                try:
                    rating_xpath = './/span[@data-hook="rating-out-of-text"]/text() | .//span[contains(@class,"a-icon-alt")]/text()'
                    avg_rating_text = hist_container.xpath(rating_xpath)
                    print(f"DEBUG: Found {len(avg_rating_text)} average rating text elements")
                except Exception as xpath_error:
                    print(f"ERROR: Invalid XPath expression for average rating: {str(xpath_error)}")
                    avg_rating_text = []
                    
                if avg_rating_text:
                    rating_match = re.search(r'(\d+(\.\d+)?)', avg_rating_text[0])
                    if rating_match:
                        reviews_data['average_rating'] = float(rating_match.group(1))

                # Get total ratings (look for text like '3,714 global ratings')
                total_ratings_text = hist_container.xpath('.//span[@data-hook="total-review-count"]/text() | .//div[@data-hook="total-review-count"]/text()')
                if total_ratings_text:
                    count_text = total_ratings_text[0].strip()
                    num_str = ''.join(filter(lambda x: x.isdigit() or x == ',', count_text))
                    try:
                        reviews_data['total_ratings'] = int(num_str.replace(',', ''))
                    except ValueError:
                         print(f"Warning: Could not parse total ratings: {count_text}")


                # Get distribution percentages from table rows
                histogram_rows = hist_container.xpath('.//table[@id="histogramTable"]//tr[contains(@class, "a-histogram-row")]')
                if histogram_rows and reviews_data['total_ratings']: # Ensure we have total ratings to calculate counts
                    for row in histogram_rows:
                        star_label_elem = row.xpath('.//td[contains(@class,"a-star-label")]/a/text()')
                        percentage_elem = row.xpath('.//td[contains(@class,"a-text-right")]/a/text()')

                        if star_label_elem and percentage_elem:
                            try:
                                star_text = star_label_elem[0].strip()
                                percent_text = percentage_elem[0].strip()

                                stars = int(star_text.split()[0])
                                percentage = int(percent_text.replace('%', ''))

                                reviews_data['distribution'][stars] = {
                                    'percentage': percentage,
                                    'count': round((percentage / 100.0) * reviews_data['total_ratings']) # Calculate count
                                }
                            except (ValueError, IndexError, TypeError):
                                print(f"Warning: Could not parse histogram row: star='{star_label_elem}', percent='{percentage_elem}'")

                # Only add if we have some data, especially distribution
                if reviews_data['distribution']:
                    # Fill in missing avg/total if possible from main section
                    if reviews_data['average_rating'] is None:
                         reviews_data['average_rating'] = main_product_details_section.get('average_rating')
                    if reviews_data['total_ratings'] is None:
                         reviews_data['total_ratings'] = main_product_details_section.get('number_of_ratings')
                    product_details['reviews_histogram_section'] = reviews_data
                    print(f"DEBUG: Extracted {len(reviews_data['distribution'])} distribution points")
        except Exception as e:
            print(f"ERROR in reviews histogram extraction: {str(e)}")

        # --- Product Information (Technical & Additional Combined) ---
        print("DEBUG: Parsing product information tables")
        try:
            product_info = {} # Initialize the dictionary to store combined info

            # Function to process a details table with better error handling
            def process_details_table(table_xpath, target_dict):
                try:
                    details_table = tree.xpath(table_xpath)
                    print(f"DEBUG: Found {len(details_table)} tables for xpath: {table_xpath}")
                    
                    if details_table:
                        try:
                            rows = details_table[0].xpath('.//tr')
                            print(f"DEBUG: Found {len(rows)} rows in table")
                        except Exception as xpath_error:
                            print(f"ERROR: Invalid XPath expression for table rows: {str(xpath_error)}")
                            rows = []
                            
                        for row in rows:
                            try:
                                key_th = row.xpath('./th')
                                value_td = row.xpath('./td')
                                
                                if key_th and value_td:
                                    # Get raw text content and clean it thoroughly
                                    key = key_th[0].text_content()
                                    value = value_td[0].text_content()

                                    # Clean key: remove leading/trailing whitespace, collapse internal whitespace/newlines
                                    key = re.sub(r'\s+', ' ', key).strip()
                                    # Clean value: remove leading/trailing whitespace, collapse internal whitespace/newlines
                                    value = re.sub(r'\s+', ' ', value).strip()
                                    
                                    # Remove special Unicode control characters like U+200E (Left-to-right mark)
                                    # and other invisible formatting characters
                                    key = clean_unicode_control_chars(key)
                                    value = clean_unicode_control_chars(value)

                                    if key and value:
                                        print(f"DEBUG: Processing table row: {key[:20]}...")
                                        # Handle special cases within the loop for clarity
                                        if key == 'Customer Reviews':
                                            rating_elem = value_td[0].xpath('.//span[@class="a-icon-alt"]/text()') # Look for 'X.X out of 5 stars'
                                            count_elem = value_td[0].xpath('.//span[@id="acrCustomerReviewText"]/text()') # Look for 'X,XXX ratings'
                                            if rating_elem and count_elem:
                                                rating_match = re.search(r'(\d+(\.\d+)?)', rating_elem[0])
                                                count_match = re.search(r'([\d,]+)\s+ratings', count_elem[0])
                                                if rating_match and count_match:
                                                    try:
                                                        target_dict['Customer Reviews'] = {
                                                            'rating': float(rating_match.group(1)),
                                                            'count': int(count_match.group(1).replace(',', ''))
                                                        }
                                                        continue # Skip adding the raw text value
                                                    except ValueError:
                                                        pass # Fall through to add raw text if parsing fails

                                        elif key == 'Best Sellers Rank':
                                            # Extract ranks more reliably, handling multiple ranks and links
                                            ranks_list = []
                                            rank_spans = value_td[0].xpath('.//span/span') # Target the inner spans containing ranks
                                            current_rank = ""
                                            for span in rank_spans:
                                                text_content = span.text_content().strip()
                                                text_content = clean_unicode_control_chars(text_content)
                                                if text_content.startswith('#'):
                                                    # If we already have a rank being built, add it first
                                                    if current_rank:
                                                        ranks_list.append(current_rank.strip())
                                                    # Start new rank
                                                    current_rank = text_content
                                                elif text_content.startswith('in ') and current_rank:
                                                    # Append category to the current rank
                                                    current_rank += f" {text_content}"
                                                else: # Handle cases where text might be split differently
                                                     if current_rank:
                                                         current_rank += f" {text_content}"


                                            # Add the last built rank if any
                                            if current_rank:
                                                ranks_list.append(current_rank.strip())

                                            if ranks_list:
                                                # Store as list if multiple, or single string if one
                                                ranks_list = [clean_unicode_control_chars(rank) for rank in ranks_list]
                                                target_dict['Best Sellers Rank'] = ranks_list[0] if len(ranks_list) == 1 else ranks_list
                                                continue # Skip adding the raw text value


                                        # Add the cleaned key-value pair if not handled specially
                                        target_dict[key] = value

                            except Exception as row_error:
                                print(f"ERROR: Problem processing table row: {str(row_error)}")
                                continue
                except Exception as table_error:
                    print(f"ERROR: Failed to process table with xpath {table_xpath}: {str(table_error)}")

            # Process Technical Details Table
            print("DEBUG: Processing Technical Details...")
            process_details_table('//table[@id="productDetails_techSpec_section_1"]', product_info)

            # Process Additional Information Table
            print("DEBUG: Processing Additional Information...")
            process_details_table('//table[@id="productDetails_detailBullets_sections1"]', product_info)

            # --- Other Information Sections (Add to product_info if not already present) ---

            # Warranty & Support (if present)
            print("DEBUG: Parsing warranty section")
            try:
                warranty_xpath = '//div[@id="warranty_feature_div"]//div[contains(@class,"a-section")]'
                warranty_section = tree.xpath(warranty_xpath)
                print(f"DEBUG: Found {len(warranty_section)} warranty sections")
            except Exception as xpath_error:
                print(f"ERROR: Invalid XPath expression for warranty: {str(xpath_error)}")
                warranty_section = []
                
            if warranty_section:
                 warranty_text = warranty_section[0].text_content().strip()
                 warranty_text = re.sub(r'\s+', ' ', warranty_text).strip()
                 # Clean Unicode control characters from warranty text
                 warranty_text = clean_unicode_control_chars(warranty_text)
                 if warranty_text and 'warranty_information' not in product_info:
                     # Try to find a specific link if available
                     link = warranty_section[0].xpath('.//a/@href')
                     if link:
                          product_info['warranty_information'] = {'text': warranty_text, 'link': link[0]}
                     else:
                          product_info['warranty_information'] = warranty_text


            # Important Information section (if present)
            print("DEBUG: Parsing important information section")
            try:
                important_info_xpath = '//div[@id="important-information"]'
                important_info_div = tree.xpath(important_info_xpath)
                print(f"DEBUG: Found {len(important_info_div)} important information divs")
                
                if important_info_div:
                    try:
                        info_content_xpath = './/div[@class="a-section content"]/descendant-or-self::*/text()'
                        important_info_content = important_info_div[0].xpath(info_content_xpath)
                        print(f"DEBUG: Found {len(important_info_content)} text elements in important info")
                        
                        full_text = ' '.join(text.strip() for text in important_info_content if text.strip())
                        # Clean Unicode control characters from important information text
                        full_text = clean_unicode_control_chars(full_text)
                        if full_text and 'important_information' not in product_info:
                            product_info['important_information'] = full_text
                    except Exception as xpath_error:
                        print(f"ERROR: Invalid XPath expression for important info content: {str(xpath_error)}")
            except Exception as xpath_error:
                print(f"ERROR: Invalid XPath expression for important information div: {str(xpath_error)}")

            # Assign the combined information dictionary
            if product_info:
                product_details['product_information_section'] = product_info
                print(f"DEBUG: Extracted {len(product_info)} product information items")
            else:
                print("Warning: No product information found in technical or additional tables.")
        except Exception as e:
            print(f"ERROR in product information extraction: {str(e)}")

        # --- A+ Content Section ---
        print("DEBUG: Parsing A+ content")
        try:
            aplus_content = []
            # Selector to find A+ content modules (might need adjustment for different A+ versions)
            # Exclude brand story and comparison tables
            print("DEBUG: Executing complex A+ content XPath expression...")
            try:
                aplus_xpath = '//div[contains(@id, "aplus") and not(ancestor::div[@id="aplusBrandStory_feature_div"]) and not(contains(@class, "aplus-comparison-table"))]//div[contains(@class, "celwidget")]'
                aplus_containers = tree.xpath(aplus_xpath)
                print(f"DEBUG: Found {len(aplus_containers)} A+ content containers")
            except Exception as xpath_error:
                print(f"ERROR: Invalid XPath expression in A+ content: {str(xpath_error)}")
                # Try a simpler selector if the complex one fails
                try:
                    print("DEBUG: Trying simpler A+ content XPath expression...")
                    aplus_containers = tree.xpath('//div[contains(@id, "aplus")]//div[contains(@class, "celwidget")]')
                    print(f"DEBUG: Found {len(aplus_containers)} A+ content containers with simpler XPath")
                except Exception as simple_xpath_error:
                    print(f"ERROR: Even simpler A+ XPath failed: {str(simple_xpath_error)}")
                    aplus_containers = []

            for container in aplus_containers:
                # Try to determine content type within the container
                img = container.xpath('.//img[not(contains(@src, "grey.gif"))]/@data-src | .//img[not(contains(@src, "grey.gif"))]/@src')
                heading = container.xpath('.//h1/text() | .//h2/text() | .//h3/text() | .//h4/text() | .//h5/text()')
                paragraph = container.xpath('.//p/text()') # Get text directly within <p>

                img_alt = container.xpath('.//img/@alt') if img else None

                if img:
                     text = ' '.join(p.strip() for p in paragraph if p.strip()) # Combine paragraphs if image is primary
                     # Clean Unicode control characters from alt and text
                     alt_text = img_alt[0].strip() if img_alt else None
                     if alt_text:
                         alt_text = clean_unicode_control_chars(alt_text)
                     if text:
                         text = clean_unicode_control_chars(text)
                     aplus_content.append({
                         'type': 'image_with_text',
                         'url': img[0],
                         'alt': alt_text,
                         'text': text if text else None # Add associated text if found
                     })
                elif heading:
                     heading_text = heading[0].strip()
                     text = ' '.join(p.strip() for p in paragraph if p.strip())
                     # Clean Unicode control characters
                     if heading_text:
                         heading_text = clean_unicode_control_chars(heading_text)
                     if text:
                         text = clean_unicode_control_chars(text)
                     aplus_content.append({
                         'type': 'heading_with_text',
                         'heading': heading_text,
                         'text': text if text else None
                     })
                elif paragraph:
                     # Only add paragraph if it wasn't associated with an image or heading above
                     text = ' '.join(p.strip() for p in paragraph if p.strip())
                     if text and not any(item.get('text') == text for item in aplus_content): # Avoid duplicates
                         # Clean Unicode control characters
                         text = clean_unicode_control_chars(text)
                         aplus_content.append({'type': 'text', 'text': text})

            if aplus_content:
                product_details['aplus_content'] = aplus_content
                print(f"DEBUG: Extracted {len(aplus_content)} A+ content items")
        except Exception as e:
            print(f"ERROR in A+ content extraction: {str(e)}")


        # --- Brand Story Section ---
        print("DEBUG: Parsing brand story section")
        try:
            brand_story_section = {}
            try:
                brand_story_div = tree.xpath('//div[@id="aplusBrandStory_feature_div"]')
                print(f"DEBUG: Found {len(brand_story_div)} brand story divs")
            except Exception as xpath_error:
                print(f"ERROR: Invalid XPath expression in brand story: {str(xpath_error)}")
                brand_story_div = []

            if brand_story_div:
                container = brand_story_div[0]
                # Get the hero image
                try:
                    hero_image = container.xpath('.//div[contains(@class, "apm-brand-story-hero")]//img')
                    print(f"DEBUG: Found {len(hero_image)} hero images in brand story")
                except Exception as xpath_error:
                    print(f"ERROR: Invalid XPath expression for hero image: {str(xpath_error)}")
                    hero_image = []

                if hero_image:
                    alt_text = hero_image[0].get('alt', '').strip()
                    # Clean Unicode control characters from alt text
                    alt_text = clean_unicode_control_chars(alt_text)
                    brand_story_section['hero_image'] = {
                        'url': hero_image[0].get('data-src') or hero_image[0].get('src'), # Prioritize data-src
                        'alt': alt_text
                    }

                # Get the carousel cards content
                carousel_cards = []
                try:
                    cards_xpath = './/div[contains(@class, "apm-brand-story-carousel-card")] | .//li[contains(@class, "apm-brand-story-carousel-card")]'
                    cards = container.xpath(cards_xpath) # Allow div or li
                    print(f"DEBUG: Found {len(cards)} carousel cards in brand story")
                except Exception as xpath_error:
                    print(f"ERROR: Invalid XPath expression for carousel cards: {str(xpath_error)}")
                    cards = []

                for card in cards:
                    card_data = {}
                    # Get background/main image
                    bg_image = card.xpath('.//img[contains(@class,"background")]/@src | .//img[contains(@class,"background")]/@data-src | .//img[not(contains(@class,"logo"))]/@src | .//img[not(contains(@class,"logo"))]/@data-src')
                    bg_alt = card.xpath('.//img[contains(@class,"background")]/@alt | .//img[not(contains(@class,"logo"))]/@alt')
                    if bg_image:
                         bg_alt_text = bg_alt[0].strip() if bg_alt else None
                         if bg_alt_text:
                             bg_alt_text = clean_unicode_control_chars(bg_alt_text)
                         card_data['background_image'] = {
                             'url': bg_image[0],
                             'alt': bg_alt_text
                         }

                    # Get logo image
                    logo_img = card.xpath('.//img[contains(@class, "logo")]/@src | .//img[contains(@class, "logo")]/@data-src')
                    logo_alt = card.xpath('.//img[contains(@class, "logo")]/@alt')
                    if logo_img:
                        logo_alt_text = logo_alt[0].strip() if logo_alt else None
                        if logo_alt_text:
                            logo_alt_text = clean_unicode_control_chars(logo_alt_text)
                        card_data['logo'] = {
                            'url': logo_img[0],
                            'alt': logo_alt_text
                        }

                    # Get text content (heading, paragraph)
                    heading = card.xpath('.//h3/text() | .//h4/text()')
                    paragraph = card.xpath('.//p/text()')
                    if heading:
                        heading_text = heading[0].strip()
                        heading_text = clean_unicode_control_chars(heading_text)
                        card_data['heading'] = heading_text
                    if paragraph:
                        paragraph_text = paragraph[0].strip()
                        paragraph_text = clean_unicode_control_chars(paragraph_text)
                        card_data['text'] = paragraph_text

                    # Get ASIN if linked
                    asin_link = card.xpath('.//a[contains(@href, "/dp/")]/@href')
                    if asin_link:
                        asin_match = re.search(r'/dp/([A-Z0-9]{10})', asin_link[0])
                        if asin_match:
                            card_data['linked_asin'] = asin_match.group(1)


                    if card_data: # Only add if we extracted something
                        carousel_cards.append(card_data)

                if carousel_cards:
                    brand_story_section['carousel_cards'] = carousel_cards

            if brand_story_section:
                product_details['brand_story_section'] = brand_story_section
                print(f"DEBUG: Extracted {len(brand_story_section['carousel_cards'])} brand story items")
        except Exception as e:
            print(f"ERROR in brand story extraction: {str(e)}")

        print("DEBUG: All XPath expressions processed without errors")
        return product_details
        
    except Exception as e:
        print(f"CRITICAL ERROR in parse_product_details: {str(e)}")
        import traceback
        traceback.print_exc()
        return {}


# --- Main execution block for testing ---
if __name__ == "__main__":
    # Test parse_product_details with the specified file
    # Use a file that includes both technical and additional details
    # test_file = 'output/product_page_B0C83J8YF8.html' # Your example file likely works
    test_file = 'path/to/your/test/B0C83J8YF8_page.html' # CHANGE THIS PATH

    if not os.path.exists(test_file):
         print(f"Error: Test file not found at {test_file}")
         print("Please download the HTML source of the product page (e.g., B0C83J8YF8 on amazon.in) and save it.")
         print("Then update the 'test_file' variable in the script.")
    else:
        try:
            with open(test_file, 'r', encoding='utf-8') as f:
                html_content = f.read()

            # --- Testing parse_product_details ---
            print("\n--- Testing parse_product_details ---")
            try:
                print("DEBUG: About to call parse_product_details...")
                product_details = parse_product_details(html_content)
                print("DEBUG: parse_product_details completed successfully!")
                print("\nParsed Product Details JSON Output:")
                # Use ensure_ascii=False for non-Latin characters if needed
                print(json.dumps(product_details, indent=2, ensure_ascii=False))
            except Exception as e:
                print(f"\nERROR: parse_product_details failed with exception: {str(e)}")
                print("\nTraceback:")
                import traceback
                traceback.print_exc()
                
                # Try to diagnose XPath issues specifically
                print("\nAttempting to diagnose potential XPath issues...")
                try:
                    test_tree = html.fromstring(html_content)
                    # Test some basic XPath expressions that should work in any valid HTML
                    print(f"Basic XPath test - //body: {len(test_tree.xpath('//body'))}")
                    print(f"Basic XPath test - //div: {len(test_tree.xpath('//div'))}")
                    print(f"Basic XPath test - //span: {len(test_tree.xpath('//span'))}")
                    print("Basic XPath tests passed successfully")
                except Exception as xpath_diagnostic_error:
                    print(f"XPath diagnostic tests failed: {str(xpath_diagnostic_error)}")
                    print("This indicates a fundamental issue with the HTML parsing or XPath functionality")

            # Optional: Check if technical details were parsed
            if 'product_details' in locals() and 'product_information_section' in product_details:
                print("\nChecking for specific technical details:")
                tech_keys_to_check = ["Model", "Product Dimensions", "Operating System", "Resolution"]
                info_section = product_details['product_information_section']
                for key in tech_keys_to_check:
                    if key in info_section:
                        print(f"  Found '{key}': {info_section[key]}")
                    else:
                        print(f"  '{key}' NOT FOUND in product_information_section.")
            else:
                 print("\n'product_information_section' not found in output.")


            # --- Optional: Testing parse_offers (if applicable HTML is in the file) ---
            # print("\n--- Testing parse_offers ---")
            # offers_json, has_prime_filter = parse_offers(html_content) # Assuming parse_offers uses the same HTML
            # print("\nParsed Offers JSON Output:")
            # print(offers_json)
            # print(f"Has Prime Filter: {has_prime_filter}")


        except FileNotFoundError:
            # This check is now done before opening the file
            pass
        except html.etree.ParserError as e:
            print(f"HTML Parsing Error: {e}. The HTML might be malformed.")
        except Exception as e:
            print(f"\nAn unexpected error occurred during file processing: {str(e)}")
            import traceback
            traceback.print_exc()