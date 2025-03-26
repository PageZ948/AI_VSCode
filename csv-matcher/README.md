# CSV Matcher Tool

A web-based tool that matches values in a CSV file against a built-in ONVIF device database and enhances the original data with profile information.

## Features

- Upload your CSV file to be enhanced
- Built-in database with over 80,000 ONVIF compliant devices
- Simply select which column in your file contains the device model/name
- Automatically matches against the "product_name" column in the database
- **Fuzzy matching** for items that don't have an exact match
- Adds the "profiles" information from the database to your data
- Color-codes results based on the number of matched profiles
- Download the enhanced CSV file with all the original data plus the matched values

## How It Works

1. **Upload File**: Upload your CSV file that contains device information
2. **Select Column**: Choose which column in your file contains the device model or product name
3. **Process**: The tool first tries to find exact matches in the database's "product_name" column. For items without an exact match, it uses fuzzy matching to find the closest match. It then adds the corresponding "profiles" information.
4. **Download**: Get your enhanced CSV file with all the original data plus the matched profiles

## Color Coding

Results are color-coded based on the number of profiles found:
- **Green**: 3 or more profiles
- **Yellow**: 2 profiles
- **Blue**: 1 profile
- **No color**: No matching device found

## Installation and Usage

### Prerequisites

- Python 3.6 or higher
- Flask
- pandas
- rapidfuzz (for fuzzy matching)

### Installation

1. Clone or download this repository
2. Install the required packages:

```bash
pip install -r requirements.txt
```

### Running the Application

1. Navigate to the project directory
2. Run the Flask application:

```bash
python app.py
```

3. Open your web browser and go to `http://127.0.0.1:5000/`
4. Follow the on-screen instructions to upload and process your CSV files

## Example Use Case

This tool is particularly useful for scenarios like:
- Matching device models with their compatible profiles
- Enriching customer data with additional information from a reference database
- Adding product details to order lists
- Any situation where you need to match values between two CSV files and combine the data

## Sample File

A sample CSV file is included to help you test the application:

`sample_main.csv` - A sample file with device information:
- Contains columns: DeviceID, DeviceModel, Manufacturer, Location
- Use "DeviceModel" as your match column

The built-in database contains ONVIF device information with:
- "product_name" column (automatically used for matching)
- "profiles" column (automatically added to your results)
- And other information like application_type, version, and approval_date

To test the application with the sample file:
1. Start the application
2. Upload `sample_main.csv` as the CSV File
3. Select "DeviceModel" as your match column
4. Process the file and view the results

## Notes

- The tool creates an "uploads" directory to temporarily store uploaded and processed files
- Files are automatically cleaned up when you click "Start Over"
- For large files, processing may take a moment
- Fuzzy matching is used when an exact match isn't found, helping to match items with typos or slight variations
- Results that used fuzzy matching will be marked with "(fuzzy match: 'source')" in the Notes column, showing which database entry was matched