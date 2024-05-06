import threading
import requests
from bs4 import BeautifulSoup
import re
import pandas as pd
import psycopg2
from concurrent.futures import ThreadPoolExecutor
import time

# Initialize a global lock for printing
print_lock = threading.Lock()

def fetch_links(url, language, page_num):
    """
    Read one page from url with the specified language, collecting all the teachers links to their personal cards for this page_num.
    Each teacher link contains substring "en/teacher/\d+/{language}", e.g. english teachers links must be like "/en/teacher/6454492/english"
    Each teacher personal card contains all necessary info about the teacher:
    - Name
    - Number of lessons
    - Number of students
    - Rating
    - Number of reviews
    - Attendance(%)	
    - Response(%)
    - Price (USD)

    Return: 
    teachers_links_per_page: list of links on teachers personal cards who teach specified language for the specified page_num
    page_num: number of page from where teachers links were retrieved
    """

    teachers_links_per_page = []
    response = requests.get(f"{url}/{language}?page={page_num}")
    if response.status_code != 200:
        with print_lock:
            print("Error: page doesn't load properly")
        return [], page_num

    # Check if we've reached the end of the pages
    phrase = "We couldn’t find any teachers for this language. Want to try another?"
 
    if phrase in response.text:
        return None, page_num  # Signal that we've reached the end

    soup = BeautifulSoup(response.text, "lxml")
    href_elements = soup.select('[href]')
    filter = re.compile(rf'^/en/teacher/\d+/{language}$')

    for element in href_elements:
        link = element.get('href')
        if filter.match(link):
            teachers_links_per_page.append(f"https://www.italki.com{link}")

    return teachers_links_per_page, page_num


def get_teachers_links(url, language):
    """
    Manages threading using ThreadPoolExecutor. It submits tasks for 10 pages at a time and waits for all tasks 
    to complete before moving to the next set of pages. 
    If None is returned by any task, it stops further submission.
    max_workers: This is set to 10, which means up to 10 threads can run concurrently.

    Return: 
    teachers_links: list of links on teachers personal cards who teach specified language for all possible pages.
    """
    
    page_num = 1
    teachers_links = []
    end_reached = False
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        while not end_reached:
            futures = [executor.submit(fetch_links, url, language, num) for num in range(page_num, page_num+10)]
            page_num += 10

            for future in futures:
                result = future.result()
                if result[0] is None:
                    end_reached = True
                    with print_lock:
                        print(f"All '{language}' teachers links were extracted, overall num = {len(set(teachers_links))}, last page_num = {result[1]}")
                    break
                teachers_links.extend(result[0])
            
    teachers_links = list(set(teachers_links))
    return teachers_links

def get_all_teachers_links(url, languages):
    """
    run get_teachers_links() for each language from languages

    Return: 
    all_teachers_links: links to teachers personal card for each language from languages
    """

    all_teachers_links = []
    for language in languages:
        all_teachers_links.extend(get_teachers_links(url, language))

    return all_teachers_links

def create_table_teachers_languages(all_teachers_links):
    """
    Create a table where with columns:
    - teacher_language_id: number of unique record (starting from 1) 
    - teacher_id: personal number of teacher (all teachers have their personal number on https://www.italki.com/,
      that can be obtained from teacher link to his/her personal card. Column teacher_id can contain non-unique values,
      because some teachers can teach multiple languages)
    - language_id: abbreviation of language
    """

    # Mapping full language names to their abbreviations
    language_map = {
        'english': 'eng',
        'spanish': 'sp',
        'japanese': 'jpn',
        'italian': 'it',
        'russian': 'ru'
    }

    # Extracting data from links
    data = []
    for index, link in enumerate(all_teachers_links, start=1):
        # Regex to extract the teacher ID and language
        match = re.search(r'/teacher/(\d+)/(\w+)', link)
        if match:
            teacher_id = int(match.group(1))
            language = str(match.group(2).lower())
            # Map the language to its abbreviation
            language_id = language_map.get(language, 'unknown')
            data.append([index, teacher_id, language_id])

    # Create DataFrame
    df = pd.DataFrame(data, columns=['teachers_languages_id', 'teacher_id', 'language_id'])
    return df

def param_process(param):
    """
    processing the values from the teachers cards:
    '1,496' -> 1496
    '12.7k' -> 1270
    '525' -> 525

    Return:
    param: processed value    
    """
    
    if "," in param:
        param = int(param.replace(",", ""))
        
    elif "k" in param:
        param_num = param.replace("k", "")
        param = int(float(param_num) * 1000)
        
    else:
        param = int(param)        
    return param
    

def get_teacher_info(teacher_link):
    """
    Using link on teachers card, extract necessary parameters for this teacher:
    Name, Rating, Students, Lessons, Attendance, Response, Reviews, Price.
    Then create a dictionary for this teacher using extracted values.
    
    Return: the dictionary, where this dictionary contains info about some teacher.
    """

    teacher_dict = {}
    response = requests.get(teacher_link)
    if response.status_code != 200:
        return None  # Handle HTTP errors

    soup = BeautifulSoup(response.text, 'html.parser')

    list_params = []
    # Name, Rating, Students, Lessons, Attendance, Response
    for par in soup.select(".h4"):
        list_params.append(par.text.strip())

    empty_params_flag = False
    # some teachers didn't specify their Rating, Students, Lessons, Attendance, Response. So we put 0 to this parameters
    if len(list_params) == 1:
        list_params.extend([0, 0, 0, 0, 0])
        
        empty_params_flag = True

    # Reviews
    review = soup.select_one("#reviews .text-gray1")
    if review:
        list_params.append(review.text.strip())

    # Price
    price = soup.select_one(".text-lg.font-bold")
    if price:
        list_params.append(price.text.strip())

    
    # fill in the dictionary
    teacher_dict["teacher_id"] = int(re.search(r'/teacher/(\d+)', teacher_link).group(1))
    teacher_dict["name"] = list_params[0]

    if not empty_params_flag:
        teacher_dict["rating"] = float(list_params[1])
        teacher_dict["students"] = param_process(list_params[2])
        teacher_dict["lessons"] = param_process(list_params[3])
        teacher_dict["attendance"] = int(re.search(r'\d+', list_params[4]).group())
        teacher_dict["response"] = int(re.search(r'\d+', list_params[5]).group())

    else: # in case of None values for rating, students, lessons, attendance, response
        teacher_dict["rating"] = list_params[1]
        teacher_dict["students"] = list_params[2]
        teacher_dict["lessons"] = list_params[3]
        teacher_dict["attendance"] = list_params[4]
        teacher_dict["response"] = list_params[5]


    reviews_text = re.search(r'\d+', list_params[6])
    teacher_dict["reviews"] = 0 if reviews_text is None else param_process(reviews_text.group())

    price_text = re.search(r'\d+\.\d+', list_params[7])
    teacher_dict["price"] = 0.0 if price_text is None else float(price_text.group())

    # Process to strip off the language part, so
    # https://www.italki.com/en/teacher/7525061/spanish -> https://www.italki.com/en/teacher/7525061
    teacher_dict["link"] = teacher_link.rsplit('/', 1)[0]
    
    return teacher_dict

def create_table_teachers(all_teachers_links):
    """
    Manages threading using ThreadPoolExecutor by running process_teacher_link() for 10 threads at the same time. 
    It submits tasks for 10 teachers links at a time and waits for all tasks 
    to complete before moving to the next set of links. 
    max_workers: This is set to 10, which means up to 10 threads can run concurrently.

    Return: 
    teachers_df: a DataFrame made with list of dicts where each dict contains all info about the teacher.
    """
    teachers_dicts = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(get_teacher_info, all_teachers_links))

    # Filter out None results and extend the list
    teachers_dicts.extend([result for result in results if result is not None])

    teachers_df = pd.DataFrame(teachers_dicts)
    # each row in table teachers_df must represent unique teacher
    teachers_df = teachers_df.drop_duplicates(['teacher_id'])
    return teachers_df

def load_data_to_postgres(df, table_name, database, user, password, host='localhost'):
    """
    Load data from a pandas DataFrame to a PostgreSQL table using psycopg2.
    We skip rows where the primary key already exists in the database.

    Args:
    df (pandas.DataFrame): DataFrame containing the data to load.
    table_name (str): Name of the target table in the PostgreSQL database.
    database (str): Name of the PostgreSQL database.
    user (str): Username for the database.
    password (str): Password for the database.
    host (str): Database server host (default is 'localhost').
    """
    # Connect to the PostgreSQL database
    conn = psycopg2.connect(database=database, user=user, password=password, host=host)
    cur = conn.cursor()
    
    # Prepare the INSERT INTO statement with ON CONFLICT DO NOTHING
    cols = ','.join(df.columns)
    values = ','.join(['%s'] * len(df.columns))
    query = f"INSERT INTO {table_name} ({cols}) VALUES ({values}) ON CONFLICT ({df.columns[0]}) DO NOTHING"

    # Execute the query row by row to track progress
    rows_loaded_num = 0
    rows_skipped_num = 0
    for row in df.itertuples(index=False, name=None):
        cur.execute(query, row)
        if cur.rowcount > 0:  # rowcount is 0 if the row was not inserted due to a conflict
            rows_loaded_num += 1
        else:
            rows_skipped_num += 1
        conn.commit()  # Commit each row to ensure data consistency, can be moved outside the loop for performance

    # Close the connection
    cur.close()
    conn.close()
    print(f"Data successfully loaded into {table_name}, {rows_loaded_num} rows were loaded, {rows_skipped_num} were skipped")

# Example usage
if __name__ == "__main__":

    start_time = time.time()  # Record the start time

    url = "https://www.italki.com/en/teachers/"
    languages = ['english', 'spanish', 'russian', 'japanese', 'italian']

    # get all teachers links to their personal card
    all_teachers_links = get_all_teachers_links(url, languages)
    print(f"All teachers links were collected, overall num = {len(all_teachers_links)}")

    # create table teachers_languages
    teachers_languages_df = create_table_teachers_languages(all_teachers_links)
    print(f"Dataframe teachers_languages_df was created [{teachers_languages_df.shape[0]} rows x {teachers_languages_df.shape[1]} columns]")

    # create table languages
    languages = {
        'language_id': ['eng', 'sp', 'ru', 'jpn', 'it'],
        'language': ['English', 'Spanish', 'Russian', 'Japanese', 'Italian']
    }
    languages_df = pd.DataFrame(languages)
    print(f"Dataframe languages was created [{languages_df.shape[0]} rows x {languages_df.shape[1]} columns]")

    # create table teachers
    teachers_df = create_table_teachers(all_teachers_links)
    print(f"Dataframe teachers was created [{teachers_df.shape[0]} rows x {teachers_df.shape[1]} columns]")    

    # load data from dataframes to each sql table
    sql_tables = ['teachers', 'languages', 'teachers_languages']
    dataframes = [teachers_df, languages_df, teachers_languages_df]
    for el in zip(dataframes, sql_tables):
        load_data_to_postgres(el[0], el[1], 'postgres', 'postgres', 'postgres')

    end_time = time.time() # Record the end time
    elapsed_time = end_time - start_time  # Calculate the elapsed time 
    print(f"Script data_load.py finished successfully with {elapsed_time} seconds to complete.")
