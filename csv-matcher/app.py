from flask import Flask, render_template, request, send_file, session, after_this_request
import pandas as pd
import os
import io
import uuid
import csv
import time
import glob
from werkzeug.utils import secure_filename
from rapidfuzz import process, fuzz

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload size
app.config['DATABASE_FILE'] = 'Database.csv'  # Hardcoded database file
app.config['DB_MATCH_COLUMN'] = 'product_name'  # Hardcoded database match column
app.config['DB_VALUE_COLUMN'] = 'profiles'  # Hardcoded database value column
app.config['FILE_RETENTION_HOURS'] = 24  # How long to keep files before cleanup

# Create uploads folder if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def cleanup_old_files():
    """Remove files older than the retention period from the uploads folder"""
    retention_seconds = app.config['FILE_RETENTION_HOURS'] * 3600
    current_time = time.time()
    
    # Get all files in the uploads directory
    upload_dir = app.config['UPLOAD_FOLDER']
    files = glob.glob(os.path.join(upload_dir, '*'))
    
    for file_path in files:
        # Skip if it's not a file
        if not os.path.isfile(file_path):
            continue
            
        # Check file age
        file_age = current_time - os.path.getmtime(file_path)
        if file_age > retention_seconds:
            try:
                os.remove(file_path)
                print(f"Removed old file: {file_path}")
            except Exception as e:
                print(f"Error removing file {file_path}: {str(e)}")

# Run cleanup on startup
cleanup_old_files()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    if 'main_file' not in request.files:
        return render_template('index.html', error='Main file is required')
    
    main_file = request.files['main_file']
    
    if main_file.filename == '':
        return render_template('index.html', error='Main file is required')
    
    # Clean up previous session files if they exist
    if 'session_id' in session:
        old_session_id = session.get('session_id')
        cleanup_session_files(old_session_id)
    
    # Save file with unique name
    session_id = str(uuid.uuid4())
    session['session_id'] = session_id
    
    main_filename = secure_filename(main_file.filename)
    main_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{session_id}_{main_filename}")
    
    main_file.save(main_path)
    session['main_path'] = main_path
    
    # Read headers for column selection
    main_headers = []
    
    try:
        with open(main_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            main_headers = next(reader)
    except Exception as e:
        return render_template('index.html', error=f'Error reading CSV headers: {str(e)}')
    
    return render_template('match.html', main_headers=main_headers)
@app.route('/process', methods=['POST'])
def process():
    if 'session_id' not in session:
        return render_template('index.html', error='Session expired. Please upload files again.')
    
    main_path = session.get('main_path')
    
    if not main_path:
        return render_template('index.html', error='Main file not found. Please upload again.')
    
    # Get column selection from form
    main_match_col = request.form.get('main_match_col')
    
    # Store the selected match column in the session for use in the result template
    session['main_match_col'] = main_match_col
    
    # Use hardcoded database columns
    db_match_col = app.config['DB_MATCH_COLUMN']
    db_value_col = app.config['DB_VALUE_COLUMN']
    
    if not main_match_col:
        return render_template('index.html', error='Please select a column from your file to match')
    
    try:
        # Read main CSV file
        main_df = pd.read_csv(main_path)
        
        # Get unique values from the main file's match column to filter database
        unique_match_values = set(main_df[main_match_col].astype(str).str.strip())
        
        # Create an empty database map for exact matches
        database_map = {}
        
        # Create a list to store all database product names for fuzzy matching
        all_db_product_names = []
        all_db_values = {}
        
        # Process database file in chunks to avoid loading the entire file
        chunk_size = 1000  # Adjust based on memory constraints
        for chunk in pd.read_csv(app.config['DATABASE_FILE'], chunksize=chunk_size):
            # Clean up product names
            chunk[db_match_col] = chunk[db_match_col].astype(str).str.strip()
            
            # Store all product names and values for fuzzy matching
            chunk_product_names = chunk[db_match_col].tolist()
            all_db_product_names.extend(chunk_product_names)
            
            # Create a dictionary of all product names and their values
            chunk_values = dict(zip(chunk[db_match_col], chunk[db_value_col]))
            all_db_values.update(chunk_values)
            
            # Filter chunk to only include rows that exactly match our main file
            matching_rows = chunk[chunk[db_match_col].isin(unique_match_values)]
            
            # Add exact matching rows to our database map
            if not matching_rows.empty:
                chunk_map = dict(zip(matching_rows[db_match_col], matching_rows[db_value_col]))
                database_map.update(chunk_map)
        
        # Function to get the best match using fuzzy matching
        def get_match(value, threshold=80):
            # First try exact match
            value_str = str(value).strip()
            exact_match = database_map.get(value_str, None)
            if exact_match:
                return exact_match, False, value_str  # Return exact match, flag that fuzzy matching wasn't used, and the exact match source
            
            # If no exact match, check if the input value matches the first word of any database entry
            for product_name in all_db_product_names:
                # Extract the first word from the database product name
                db_first_word = product_name.split()[0] if product_name.split() else product_name
                
                # Check if the input value matches the first word of the database entry
                if value_str == db_first_word:
                    return all_db_values[product_name], True, product_name
            
            # If first word match fails, then try fuzzy matching
            # Manual implementation of fuzzy matching using token_sort_ratio
            best_score = 0
            best_match = None
            
            for product_name in all_db_product_names:
                score = fuzz.token_sort_ratio(value_str, product_name)
                if score > best_score:
                    best_score = score
                    best_match = product_name
            
            # Check if the match score is above the threshold
            if best_match and best_score >= threshold:
                return all_db_values[best_match], True, best_match  # Return fuzzy match, flag that fuzzy matching was used, and the fuzzy match source
            
            return '', False, ''  # No match found
        
        # Add new columns for matched values, match type, and match source
        match_results = main_df[main_match_col].apply(lambda x: get_match(x))
        main_df['Matched_Profiles'] = match_results.apply(lambda x: x[0])
        main_df['Fuzzy_Match_Used'] = match_results.apply(lambda x: x[1])
        main_df['Match_Source'] = match_results.apply(lambda x: x[2])
        
        # Notes column removed as fuzzy match source is already in Match_Source column
        
        # Add column for color coding (will be used in the CSV download)
        def get_color_code(profiles):
            if not profiles:
                return "Red"
            count = len(str(profiles).split(','))
            if count >= 2:
                return "Green"
            elif count == 1:
                return "Yellow"
            return "Red"
        
        main_df['Color_Code'] = main_df['Matched_Profiles'].apply(get_color_code)
        main_df['Color_Code'] = main_df['Matched_Profiles'].apply(get_color_code)
        
        # Save processed file
        result_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{session['session_id']}_result.csv")
        main_df.to_csv(result_path, index=False)
        session['result_path'] = result_path
        
        # Get preview data
        preview_data = main_df.head(10).to_dict('records')
        
        return render_template('result.html',
                              preview_data=preview_data,
                              columns=main_df.columns.tolist())
    
    except Exception as e:
        return render_template('index.html', error=f'Error processing files: {str(e)}')

@app.route('/download')
def download():
    if 'result_path' not in session:
        return render_template('index.html', error='Result not found. Please process files again.')
    
    result_path = session.get('result_path')
    
    if not os.path.exists(result_path):
        return render_template('index.html', error='Result file not found.')
    
    @after_this_request
    def cleanup_after_download(response):
        # Schedule cleanup of session files after download completes
        if 'session_id' in session:
            cleanup_session_files(session.get('session_id'))
        return response
    
    return send_file(result_path,
                    mimetype='text/csv',
                    as_attachment=True,
                    download_name='matched_results.csv')

def cleanup_session_files(session_id):
    """Remove all files associated with a specific session ID"""
    if not session_id:
        return
        
    # Find all files with this session ID prefix
    upload_dir = app.config['UPLOAD_FOLDER']
    session_files = glob.glob(os.path.join(upload_dir, f"{session_id}_*"))
    
    for file_path in session_files:
        if os.path.isfile(file_path):
            try:
                os.remove(file_path)
                print(f"Removed session file: {file_path}")
            except Exception as e:
                print(f"Error removing file {file_path}: {str(e)}")

@app.route('/clear')
def clear():
    # Clean up all session files
    if 'session_id' in session:
        cleanup_session_files(session.get('session_id'))
    
    # Also clean up any specific paths stored in session
    for key in ['main_path', 'result_path']:
        if key in session and session[key] and os.path.exists(session[key]):
            try:
                os.remove(session[key])
            except Exception as e:
                print(f"Error removing file {session[key]}: {str(e)}")
    
    # Clear session
    session.clear()
    
    return render_template('index.html', message='Session cleared. All uploaded files have been removed.')

if __name__ == '__main__':
    app.run(debug=True)