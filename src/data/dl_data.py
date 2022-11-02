import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
import torch
import torch.nn as nn
from torch.utils.data import TensorDataset, DataLoader, Dataset
from src.utils import EarlyStopping
from copy import deepcopy

def age_map(x: int) -> int:
    x = int(x)
    if x < 20:
        return 1
    elif x >= 20 and x < 30:
        return 2
    elif x >= 30 and x < 40:
        return 3
    elif x >= 40 and x < 50:
        return 4
    elif x >= 50 and x < 60:
        return 5
    else:
        return 6


def year_of_publication_map(x: int) -> int:
    """
    25%        1991.000000
    50%        1996.000000
    75%        2000.000000
    max        2006.000000
    """
    x = int(x)
    if x < 1991:
        return 1
    elif x >= 1991 and x < 1996:
        return 2
    elif x >= 1996 and x < 2000:
        return 3
    else:
        return 4


def process_context_data(users, books, ratings1, ratings2):
    ratings = pd.concat([ratings1, ratings2]).reset_index(drop=True)

    # 인덱싱 처리된 데이터 조인
    context_df = ratings.merge(users, on='user_id', how='left').merge(books[['isbn', 'category', 'publisher', 'year_of_publication', 'book_author']], on='isbn', how='left')
    train_df = ratings1.merge(users, on='user_id', how='left').merge(books[['isbn', 'category', 'publisher', 'year_of_publication', 'book_author']], on='isbn', how='left')
    test_df = ratings2.merge(users, on='user_id', how='left').merge(books[['isbn', 'category', 'publisher', 'year_of_publication', 'book_author']], on='isbn', how='left')

    column_list = ['location_city', 'location_state', 'location_country', 'age', 'book_author', \
                        'year_of_publication', 'publisher', 'category']

    columns = [column for column in column_list if train_df.iloc[0][column] != -1]

    # 인덱싱 처리
    loc_city2idx = {v:k for k,v in enumerate(context_df['location_city'].unique())}
    loc_state2idx = {v:k for k,v in enumerate(context_df['location_state'].unique())}
    loc_country2idx = {v:k for k,v in enumerate(context_df['location_country'].unique())}

    train_df['location_city'] = train_df['location_city'].map(loc_city2idx)
    train_df['location_state'] = train_df['location_state'].map(loc_state2idx)
    train_df['location_country'] = train_df['location_country'].map(loc_country2idx)
    test_df['location_city'] = test_df['location_city'].map(loc_city2idx)
    test_df['location_state'] = test_df['location_state'].map(loc_state2idx)
    test_df['location_country'] = test_df['location_country'].map(loc_country2idx)

    train_df['age'] = train_df['age'].apply(age_map)
    test_df['age'] = test_df['age'].apply(age_map)

    # year of publication cases 4
    train_df['year_of_publication'] = train_df['year_of_publication'].apply(year_of_publication_map)
    test_df['year_of_publication'] = test_df['year_of_publication'].apply(year_of_publication_map)

    # book 파트 인덱싱
    category2idx = {v:k for k,v in enumerate(context_df['category'].unique())}
    publisher2idx = {v:k for k,v in enumerate(context_df['publisher'].unique())}
    author2idx = {v:k for k,v in enumerate(context_df['book_author'].unique())}

    train_df['category'] = train_df['category'].map(category2idx)
    train_df['publisher'] = train_df['publisher'].map(publisher2idx)
    train_df['book_author'] = train_df['book_author'].map(author2idx)
    test_df['category'] = test_df['category'].map(category2idx)
    test_df['publisher'] = test_df['publisher'].map(publisher2idx)
    test_df['book_author'] = test_df['book_author'].map(author2idx)

    idx = {
        "loc_city2idx":loc_city2idx,
        "loc_state2idx":loc_state2idx,
        "loc_country2idx":loc_country2idx,
        "category2idx":category2idx,
        "publisher2idx":publisher2idx,
        "author2idx":author2idx,
    }

    length_db = {'age':6, 'year_of_publication': 4, 
                'location_city': len(idx['loc_city2idx']), 'location_state': len(idx['loc_state2idx']), 
                'location_country': len(idx['loc_country2idx']), 'category': len(idx['category2idx']), 'publisher': len(idx['publisher2idx']),
                'book_author': len(idx['author2idx'])}
    field_dims = [length_db[column] for column in columns]

    return idx, train_df, test_df, columns, field_dims

def dl_data_load(args):

    ######################## DATA LOAD
    formatted_user_num = format(args.USER_NUM, '02')
    formatted_book_num = format(args.BOOK_NUM, '02')
    users = pd.read_csv(args.DATA_PATH + 'users/' + f'u{formatted_user_num}.csv')
    books = pd.read_csv(args.DATA_PATH + 'books/' + f'b{formatted_book_num}.csv')
    train = pd.read_csv(args.DATA_PATH + 'ratings/' + 'train_ratings.csv')
    test = pd.read_csv(args.DATA_PATH + 'ratings/' + 'test_ratings.csv')
    sub = pd.read_csv(args.DATA_PATH + 'ratings/' + 'sample_submission.csv')

    ids = pd.concat([train['user_id'], sub['user_id']]).unique()
    isbns = pd.concat([train['isbn'], sub['isbn']]).unique()

    idx2user = {idx:id for idx, id in enumerate(ids)}
    idx2isbn = {idx:isbn for idx, isbn in enumerate(isbns)}

    user2idx = {id:idx for idx, id in idx2user.items()}
    isbn2idx = {isbn:idx for idx, isbn in idx2isbn.items()}

    train['user_id'] = train['user_id'].map(user2idx)
    sub['user_id'] = sub['user_id'].map(user2idx)
    test['user_id'] = test['user_id'].map(user2idx)
    users['user_id'] = users['user_id'].map(user2idx)

    train['isbn'] = train['isbn'].map(isbn2idx)
    sub['isbn'] = sub['isbn'].map(isbn2idx)
    test['isbn'] = test['isbn'].map(isbn2idx)
    books['isbn'] = books['isbn'].map(isbn2idx)

    idx, context_train, context_test, columns, field_dims = process_context_data(users, books, train, test)
    """
    'user_id': len(user2idx), 'isbn': len(isbn2idx), 
    """
    columns = ['user_id', 'isbn'] + columns
    field_dims = np.array([len(user2idx), len(isbn2idx)] + field_dims, dtype = np.int64)
    context_train = context_train[columns + ['rating']]
    context_test = context_test[columns + ['rating']]

    data = {
            'train':context_train,
            'test':context_test.drop(['rating'], axis=1),
            'field_dims':field_dims,
            'users':users,
            'books':books,
            'sub':sub,
            'idx2user':idx2user,
            'idx2isbn':idx2isbn,
            'user2idx':user2idx,
            'isbn2idx':isbn2idx,
            }

    return data


def dl_data_split(args, data):
    X_train, X_valid, y_train, y_valid = train_test_split(
                                                        data['train'].drop(['rating'], axis=1),
                                                        data['train']['rating'],
                                                        test_size=args.TEST_SIZE,
                                                        random_state=args.SEED,
                                                        shuffle=True
                                                        )
    data['X_train'], data['X_valid'], data['y_train'], data['y_valid'] = X_train, X_valid, y_train, y_valid
    print(f"X_train: \n {data['X_train'].sample(10)}, len: {len(data['X_train'])}")
    return data


def dl_data_loader(args, data, cf=False, range_str='09', last_valid=False, is_boosting=False):
    new_data = deepcopy(data) 

    if last_valid:
        # last_valid 는 전체를 그냥 통과한다.
        range_str='09'
    
    if cf:        
        def convert_rating_to_label(x):
            for i, r in enumerate(data['ranges']):
                if int(r[0])+1 <= x <= int(r[1])+1:
                    return i

        # 클래시피케이션이면 라벨로 변경한다.
        #print(new_data['y_train'])
        new_data['y_train'] = new_data['y_train'].apply(convert_rating_to_label)
        new_data['y_valid'] = new_data['y_valid'].apply(convert_rating_to_label)

        train_dataset = TensorDataset(torch.LongTensor(new_data['X_train'].values), torch.LongTensor(new_data['y_train'].values))
        valid_dataset = TensorDataset(torch.LongTensor(new_data['X_valid'].values), torch.LongTensor(new_data['y_valid'].values))
    else:
        # 리그레션이면 range_str에 따라 잘라서 전달한다.
        live_indices_train =\
            new_data['y_train'][(new_data['y_train'] >= int(range_str[0])+1) & (new_data['y_train'] <= int(range_str[1])+1)].index
        
        live_indices_valid =\
            new_data['y_valid'][(new_data['y_valid'] >= int(range_str[0])+1) & (new_data['y_valid'] <= int(range_str[1])+1)].index

        
        new_data['X_train'] = new_data['X_train'].loc[live_indices_train]
        new_data['y_train'] = new_data['y_train'].loc[live_indices_train]

        new_data['X_valid'] = new_data['X_valid'].loc[live_indices_valid]
        new_data['y_valid'] = new_data['y_valid'].loc[live_indices_valid]

        # print(new_data['X_train'])
        # print(new_data['y_train'])

        if args.ZEROONE:
            new_data['y_train'] = new_data['y_train'].astype(np.float64) / 10.0
            new_data['y_valid'] = new_data['y_valid'].astype(np.float64) / 10.0
        
        # if args.RR_MODEL in ('XGB', 'LGBM', 'CATB'):
        #     new_data['train_dataloader'], new_data['valid_dataloader'], new_data['test_dataloader'] = \
        #         (new_data['X_train'], new_data['y_train']), (new_data['X_valid'], new_data['y_valid']), (new_data['test'], None)

        train_dataset = TensorDataset(torch.LongTensor(new_data['X_train'].values), torch.FloatTensor(new_data['y_train'].values))
        valid_dataset = TensorDataset(torch.LongTensor(new_data['X_valid'].values), torch.FloatTensor(new_data['y_valid'].values))
        # print(new_data['y_valid'])

    test_dataset = TensorDataset(torch.LongTensor(data['test'].values))

    train_dataloader = DataLoader(train_dataset, batch_size=args.BATCH_SIZE, shuffle=args.DATA_SHUFFLE, num_workers = 4)
    valid_dataloader = DataLoader(valid_dataset, batch_size=args.BATCH_SIZE, shuffle=args.DATA_SHUFFLE, num_workers = 4)
    test_dataloader = DataLoader(test_dataset, batch_size=args.BATCH_SIZE, shuffle=False, num_workers = 4)

    # if cf:
    #     train_dataloader = DataLoader(train_dataset, batch_size=args.CF_BATCH_SIZE, shuffle=args.DATA_SHUFFLE, num_workers = 4)
    #     valid_dataloader = DataLoader(valid_dataset, batch_size=args.CF_BATCH_SIZE, shuffle=args.DATA_SHUFFLE, num_workers = 4)
    #     test_dataloader = DataLoader(test_dataset, batch_size=args.CF_BATCH_SIZE, shuffle=False, num_workers = 4)

    # else:
    #     train_dataloader = DataLoader(train_dataset, batch_size=args.RR_BATCH_SIZE, shuffle=args.DATA_SHUFFLE, num_workers = 4)
    #     valid_dataloader = DataLoader(valid_dataset, batch_size=args.RR_BATCH_SIZE, shuffle=args.DATA_SHUFFLE, num_workers = 4)
    #     test_dataloader = DataLoader(test_dataset, batch_size=args.RR_BATCH_SIZE, shuffle=False, num_workers = 4)

    if is_boosting:
        new_data['train_dataloader'], new_data['valid_dataloader'], new_data['test_dataloader'] = \
            (new_data['X_train'], new_data['y_train']), (new_data['X_valid'], new_data['y_valid']), (new_data['test'], None)

    else:
        new_data['train_dataloader'], new_data['valid_dataloader'], new_data['test_dataloader'] = train_dataloader, valid_dataloader, test_dataloader

    return new_data
