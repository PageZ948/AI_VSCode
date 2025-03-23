from flask import Flask, render_template, request, send_file, session
import pandas as pd
import os
import io
import uuid
import csv
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload size
app.config['DATABASE_FILE'] = 'Database.csv'  # Hardcoded database file
app.config['DB_MATCH_COLUMN'] = 'product_name'  # Hardcoded database match column
app.config['DB_VALUE_COLUMN'] = 'profiles'  # Hardcoded database value column

# Create uploads folder if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

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
        
        # Create an empty database map
        database_map = {}
        
        # Process database file in chunks to avoid loading the entire file
        chunk_size = 1000  # Adjust based on memory constraints
        for chunk in pd.read_csv(app.config['DATABASE_FILE'], chunksize=chunk_size):
            # Filter chunk to only include rows that might match our main file
            chunk[db_match_col] = chunk[db_match_col].astype(str).str.strip()
            matching_rows = chunk[chunk[db_match_col].isin(unique_match_values)]
            
            # Add matching rows to our database map
            if not matching_rows.empty:
                chunk_map = dict(zip(matching_rows[db_match_col], matching_rows[db_value_col]))
                database_map.update(chunk_map)
        
        # Add new column for matched values
        main_df['Matched_Profiles'] = main_df[main_match_col].map(lambda x: database_map.get(str(x).strip(), ''))
        
        # Add column for notes
        main_df['Notes'] = main_df['Matched_Profiles'].apply(
            lambda x: f"{len(str(x).split(','))} profile{'s' if len(str(x).split(',')) != 1 else ''}" if x else "No matching device found"
        )
        
        # Add column for color coding (will be used in the CSV download)
        def get_color_code(profiles):
            if not profiles:
                return "None"
            count = len(str(profiles).split(','))
            if count >= 3:
                return "Green"
            elif count == 2:
                return "Yellow"
            elif count == 1:
                return "Blue"
            return "None"
        
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
    
    return send_file(result_path, 
                    mimetype='text/csv',
                    as_attachment=True, 
                    download_name='matched_results.csv')

@app.route('/clear')
def clear():
    # Clean up session files
    for key in ['main_path', 'database_path', 'result_path']:
        if key in session and session[key] and os.path.exists(session[key]):
            try:
                os.remove(session[key])
            except:
                pass
    
    # Clear session
    session.clear()
    
    return render_template('index.html', message='Session cleared. You can upload new files.')

if __name__ == '__main__':
    app.run(debug=True)