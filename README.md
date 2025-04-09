# Amazon Product Data Scraper

A simple tool to get product information from Amazon using ASIN numbers.

## Clone the Repository

```bash
git clone https://github.com/njraladdin/asin-product-details-scraper.git
cd asin-product-details-scraper
```

## Requirements

- Python 3.8 to 3.12 (Python 3.13 is NOT supported due to lxml compatibility issues)

## Quick Start

```bash
# 1. Create a virtual environment
# On Windows:
python -m venv venv
# On macOS/Linux:
python3 -m venv venv

# 2. Activate the virtual environment
# On Windows (Command Prompt):
venv\Scripts\activate.bat
# On Windows (PowerShell):
venv\Scripts\Activate.ps1
# On macOS/Linux:
source venv/bin/activate

# 3. Install the package with all dependencies
pip install .

# 4. Run the scraper
python main.py B09X7CRKRZ
``` 

## Detailed Usage

```bash
# Get data for one or more products
python main.py B09X7CRKRZ B07CRG7BBH

# Get data from a text file
python main.py --file examples/example.txt

# Get data from a CSV file
python main.py --file examples/example.csv
```

## Configuration

The tool uses a single configuration file:
- `config.json` - Controls basic behavior

Key settings:
- `initial_session_pool_size`: Number of initial sessions (default: 5)
- `allow_proxy`: Whether to use proxies (default: false)
- `concurrent_requests_control`: Controls request rate
  - `initial_concurrent`: Starting number of concurrent requests
  - `scale_up_delay`: Delay between scaling up requests
  - `scale_increment`: How many requests to add each time

## Output

- Data is saved in the `output` folder
- Each product gets its own JSON file named `product_ASIN_TIMESTAMP.json`
- Files contain:
  - Product details (title, price, ratings, etc.)
  - Seller offers data
  - Product variants
  - Images and media information

## Example Output Structure

```json
{
  "asin": "B09X7CRKRZ",
  "timestamp": 1744118289,
  "product_details": {
    "main_product_details_section": {
      "product_title": "...",
      "brand": "...",
      "average_rating": 4.8,
      "number_of_ratings": 116877,
      "price": 23.99,
      "feature_bullets": [...],
      "available_options": [...],
      "media": {...}
    },
    "reviews_histogram_section": {...},
    "product_information_section": {...}
  },
  "offers_data": [...]
}
```

## Notes

- The tool requires a stable internet connection
- Amazon may block requests if too many are made in a short time
- All data is saved in UTF-8 encoding
- Duplicate ASINs are automatically removed 