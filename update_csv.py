import os
import csv
from dotenv import load_dotenv
from fileMoon import FileMoon

def main():
    # Load environment variables
    load_dotenv()
    
    api_key = os.getenv("FILEMOON_API_KEY")
    if not api_key:
        print("❌ Error: FILEMOON_API_KEY not found in .env file.")
        return

    # Initialize FileMoon client
    client = FileMoon(api_key)
    csv_filename = "filemoon_files.csv"
    
    print(f"🔄 Updating {csv_filename} from FileMoon API...")
    
    try:
        with open(csv_filename, mode='w', newline='', encoding='utf-8') as csv_file:
            fieldnames = ['file_code', 'title', 'file_size', 'uploaded', 'status', 'public']
            writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
            writer.writeheader()
            
            page = 1
            total_files = 0
            
            while True:
                response = client.f_list(per_page="100", page=str(page))
                
                if not response or 'result' not in response or 'files' not in response['result']:
                    print(f"⚠️ No more files found or API error at page {page}.")
                    break
                
                files = response['result']['files']
                if not files:
                    break
                
                for file_data in files:
                    writer.writerow({
                        'file_code': file_data.get('file_code', ''),
                        'title': file_data.get('title', ''),
                        'file_size': file_data.get('file_size', ''),
                        'uploaded': file_data.get('uploaded', ''),
                        'status': file_data.get('status', ''),
                        'public': file_data.get('public', '')
                    })
                
                num_on_page = len(files)
                total_files += num_on_page
                print(f"✅ Page {page}: Fetched {num_on_page} files (Total: {total_files})")
                
                if num_on_page < 100:
                    break
                page += 1
                
        print(f"🎉 Successfully updated {csv_filename} with {total_files} files.")
        
    except Exception as e:
        print(f"❌ Error updating CSV: {e}")

if __name__ == "__main__":
    main()
