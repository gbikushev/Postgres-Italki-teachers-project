#!/usr/bin/env python3  


"""
* query1:
output all teachers that teach {language} language with the ability to specify:
 - rating [>,<,=,>=,<=] {rating}
 - students [>,<,=,>=,<=] {students}
 - lessons [>,<,=,>=,<=] {lessons}
 - attendance [>,<,=,>=,<=] {attendance}
 - response [>,<,=,>=,<=] {response}
 - reviews [>,<,=,>=,<=] {reviews}
 - price [>,<,=,>=,<=] {price}
Example of usage:
1) python data_analysis.py --query=1 --language=english --rating>4.5 --students>100 --response==100
2) python data_analysis.py --query=1 --language=russian --rating==5.0 --price<15

* query2:
output all teachers that can teach all languages that are in list {languages_list} ordered by price.
Example of usage:
1) python data_analysis.py --query=2 --languages=english,russian
2) python data_analysis.py --query=2 --languages=english,russian,spanish

* query3:
output top {limit} most paid teachers for {language}.
Example of usage:
1) python data_analysis.py --query=3 --language=english --limit=10
2) python data_analysis.py --query=3 --language=russian --limit=15

* query4:
output top {limit} teachers with the most number of students they had for {language}.
Example of usage:
1) python data_analysis.py --query=4 --language=english --limit=10
2) python data_analysis.py --query=4 --language=russian --limit=5

"""

import argparse
import pandas as pd
import psycopg2 as pg
import re
import sys


def parse_operator_arg(value):
    # This function parses the argument to extract the operator and the value
    match = re.match(r'([<>=]+)([\d\.]+)', value)
    if not match:
        raise argparse.ArgumentTypeError("Invalid format for operator argument")
    return match.groups()

if __name__ == '__main__':
    conn = pg.connect(database='postgres', user='postgres', password='postgres')

    parser = argparse.ArgumentParser(description='make queries to data')
    parser.add_argument('--query', type=int, default=1)
    parser.add_argument('--language', type=str, default='english')
    
    # Change arguments to accept strings and parse them using the custom function
    parser.add_argument('--rating', type=parse_operator_arg)
    parser.add_argument('--students', type=parse_operator_arg)
    parser.add_argument('--lessons', type=parse_operator_arg)
    parser.add_argument('--attendance', type=parse_operator_arg)
    parser.add_argument('--response', type=parse_operator_arg)
    parser.add_argument('--reviews', type=parse_operator_arg)
    parser.add_argument('--price', type=parse_operator_arg)

    parser.add_argument('--limit', type=int, default=10)
    parser.add_argument('--languages', type=str,  default='english,russian')

    args = parser.parse_args()

    # allowed signs for args: rating, students, attendance, response, reviews, price
    allowed_signs = ['=', '>', '<', '>=', '<=']

    allowed_languages = ['english', 'spanish', 'japanese', 'italian', 'russian']

    if args.language not in allowed_languages:
        sys.exit(f'Error: {args.language} is not in list of supported languages. \nSupported languages are {allowed_languages}')

    if args.query == 1:
        
        select_query = \
            f"SELECT teachers.*, languages.language\
            FROM teachers\
            JOIN teachers_languages ON teachers.teacher_id=teachers_languages.teacher_id\
            JOIN languages ON languages.language_id=teachers_languages.language_id\
            WHERE languages.language = '{args.language.capitalize()}'"
      

        teacher_args = vars(args)
        teacher_args.pop('query')
        teacher_args.pop('language')
        teacher_args.pop('limit')
        teacher_args.pop('languages')

        for arg, sign_value in teacher_args.items():

            # choose all args that are not None
            if sign_value is None:
                continue

            sign, value = sign_value[0], sign_value[1]

            if sign not in allowed_signs:
                sys.exit(f'Error: {sign} is incorrect sign used for. Have a look at README file.')

            select_query += f' AND teachers.{arg} {sign} {value}'

        select_query += ';'
        
        df = pd.read_sql_query(select_query, conn)
        print(df)

    elif args.query == 2:
        languages = tuple(args.languages.split(','))
        
        for language in languages:
            if language not in allowed_languages:
                sys.exit(f'Error: {language} is not in list of supported languages. \nSupported languages are {allowed_languages}')
        languages = tuple(map(lambda x: x.capitalize(), languages))

        select_query = \
        f"SELECT teachers.*,\
        string_agg(languages.language::text, ', ' ORDER BY languages.language) AS languages\
        FROM teachers\
        JOIN teachers_languages ON teachers.teacher_id = teachers_languages.teacher_id\
        JOIN languages ON teachers_languages.language_id = languages.language_id\
        WHERE languages.language IN {languages}\
        GROUP BY teachers.teacher_id\
        HAVING COUNT(DISTINCT languages.language) = {len(languages)}\
        ORDER BY teachers.price;"

        df = pd.read_sql_query(select_query, conn)
        print(df)


    elif args.query == 3:
        select_query = \
        f"SELECT teachers.*, languages.language\
        FROM teachers\
        JOIN teachers_languages ON teachers.teacher_id=teachers_languages.teacher_id\
        JOIN languages ON languages.language_id=teachers_languages.language_id\
        WHERE languages.language = '{args.language.capitalize()}'\
        ORDER BY teachers.price DESC\
        LIMIT {args.limit}"

        df = pd.read_sql_query(select_query, conn)
        print(df)

        
    elif args.query == 4:
        select_query = \
        f"SELECT teachers.*, languages.language\
        FROM teachers\
        JOIN teachers_languages ON teachers.teacher_id=teachers_languages.teacher_id\
        JOIN languages ON languages.language_id=teachers_languages.language_id\
        WHERE languages.language = '{args.language.capitalize()}'\
        ORDER BY teachers.students DESC\
        LIMIT {args.limit}"

        df = pd.read_sql_query(select_query, conn)
        print(df)
    else:
        print('Error: value {args.query} is incorrect value for --query argument. Have a look at README file.')


