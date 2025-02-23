from email.policy import default
import time
import argparse
import pandas as pd
import numpy as np

from src import seed_everything

from src.data import context_data_load, context_data_split, context_data_loader
from src.data import dl_data_load, dl_data_split, dl_data_loader
from src.data import image_data_load, image_data_split, image_data_loader
from src.data import text_data_load, text_data_split, text_data_loader

from src import FactorizationMachineModel, FieldAwareFactorizationMachineModel
from src import NeuralCollaborativeFiltering, WideAndDeepModel, DeepCrossNetworkModel
from src import CNN_FM
from src import DeepCoNN

from src import XGBoostModel, LightGBMModel, CatBoostModel

from sklearn.model_selection import StratifiedKFold


class StandardScaler:
    def __init__(self):
        self.train_mean = None
        self.train_std = None

    def build(self, train_data):
        self.train_mean = train_data.mean()
        self.train_std = train_data.std()

    def normalize(self, df):
        return (df - self.train_mean) / self.train_std


def main(args):
    seed_everything(args.SEED)

    ######################## DATA LOAD
    print(f'--------------- {args.MODEL} Load Data ---------------')
    if args.MODEL in ('FM', 'FFM', 'XGB', 'LGBM', 'CATB'):
        data = context_data_load(args)
    elif args.MODEL in ('NCF', 'WDN', 'DCN'):
        data = dl_data_load(args)
    elif args.MODEL == 'CNN_FM':
        data = image_data_load(args)
    elif args.MODEL == 'DeepCoNN':
        import nltk
        nltk.download('punkt')
        data = text_data_load(args)
    else:
        pass

    if args.VALID == 'random':
        ######################## Train/Valid Split
        print(f'--------------- {args.MODEL} Train/Valid Split ---------------')
        if args.MODEL in ('FM', 'FFM', 'XGB', 'LGBM', 'CATB'):
            data = context_data_split(args, data)
            data = context_data_loader(args, data)

        elif args.MODEL in ('NCF', 'WDN', 'DCN'):
            data = dl_data_split(args, data)
            data = dl_data_loader(args, data)

        elif args.MODEL=='CNN_FM':
            data = image_data_split(args, data)
            data = image_data_loader(args, data)

        elif args.MODEL=='DeepCoNN':
            data = text_data_split(args, data)
            data = text_data_loader(args, data)
            scaler = data['scaler']
        else:
            pass


        ######################## Model
        print(f'--------------- INIT {args.MODEL} ---------------')
        if args.MODEL=='FM':
            model = FactorizationMachineModel(args, data)
        elif args.MODEL=='FFM':
            model = FieldAwareFactorizationMachineModel(args, data)
        elif args.MODEL=='NCF':
            model = NeuralCollaborativeFiltering(args, data)
        elif args.MODEL=='WDN':
            model = WideAndDeepModel(args, data)
        elif args.MODEL=='DCN':
            model = DeepCrossNetworkModel(args, data)
        elif args.MODEL=='CNN_FM':
            model = CNN_FM(args, data)
        elif args.MODEL=='DeepCoNN':
            model = DeepCoNN(args, data)
        elif args.MODEL=='XGB':
            model = XGBoostModel(args, data)
        elif args.MODEL=='LGBM':
            model = LightGBMModel(args, data)
        elif args.MODEL=='CATB':
            model = CatBoostModel(args, data)
        else:
            pass

        ######################## TRAIN
        if args.ZEROONE:
            print('zeroone')
        else:
            print('no zeroone')

        if args.LOSS == 'sl1':
            print('with sl1 loss beta', args.BETA)
        elif args.LOSS == 'rmse':
            print('with rmse loss')
        print(f'--------------- {args.MODEL} TRAINING ---------------')
        model.train(fold_num = 0)

        ######################## INFERENCE
        print(f'--------------- {args.MODEL} PREDICT ---------------')
        if args.MODEL in ('FM', 'FFM', 'NCF', 'WDN', 'DCN', 'XGB', 'LGBM', 'CATB'):
            predicts = model.predict(data['test_dataloader'])
        elif args.MODEL=='CNN_FM':
            predicts  = model.predict(data['test_dataloader'])
        elif args.MODEL=='DeepCoNN':
            predicts  = model.predict(data['test_dataloader'])

        else:
            pass
        predicts = np.array(predicts)
        if args.CLASSIFIER:
            predicts = predicts + 1
        if args.SCALER:
            predicts = predicts * scaler.train_std + scaler.train_mean
        predicts = predicts.tolist()

        ######################## SAVE PREDICT
        print(f'--------------- SAVE {args.MODEL} PREDICT ---------------')
        submission = pd.read_csv(args.DATA_PATH + 'ratings/sample_submission.csv')
        if args.MODEL in ('FM', 'FFM', 'NCF', 'WDN', 'DCN', 'CNN_FM', 'DeepCoNN', 'XGB', 'LGBM', 'CATB'):
            if args.ZEROONE: # 0. ~ 1 스케일링 시
                submission['rating'] = [p * 10 for p in predicts]
            else:
                submission['rating'] = [p for p in predicts]
        else:
            pass

    elif args.VALID == 'kfold':
        skf = StratifiedKFold(n_splits = args.N_SPLITS, shuffle = True)
        length = len(data['test'])
        kfold_predicts = np.zeros((args.N_SPLITS, length))
        rmse_array = np.zeros(args.N_SPLITS)

        if args.LOSS == 'sl1':
            print('with sl1 loss beta', args.BETA)
        elif args.LOSS == 'rmse':
            print('with rmse loss')

        if args.MODEL in ('FM', 'FFM', 'XGB', 'LGBM', 'CATB'):
            for idx, (train_index, valid_index) in enumerate(skf.split(
                                                data['train'].drop(['rating'], axis = 1),
                                                data['train']['rating']
                                                )):
                
                data['X_train']= data['train'].drop(['rating'], axis = 1).iloc[train_index]
                data['y_train'] = data['train']['rating'].iloc[train_index]
                data['X_valid']= data['train'].drop(['rating'], axis = 1).iloc[valid_index]
                data['y_valid'] = data['train']['rating'].iloc[valid_index]
                data = context_data_loader(args, data)

                print(f'--------------- FOLD-{idx}, INIT {args.MODEL} ---------------')
                if args.MODEL=='FM':
                    model = FactorizationMachineModel(args, data)
                elif args.MODEL=='FFM':
                    model = FieldAwareFactorizationMachineModel(args, data)
                elif args.MODEL=='XGB':
                    model = XGBoostModel(args, data)
                elif args.MODEL=='LGBM':
                    model = LightGBMModel(args, data)
                elif args.MODEL=='CATB':
                    model = CatBoostModel(args, data)
                else:
                    pass
                
                print(f'--------------- FOLD-{idx}, {args.MODEL} TRAINING ---------------')
                rmse_score = model.train(fold_num = idx)
                rmse_array[idx] = rmse_score
                
                print(f'--------------- FOLD-{idx}, {args.MODEL} PREDICT ---------------')
                kfold_predicts[idx] = np.array(model.predict(data['test_dataloader']))
            
            
            
            print(f'--------------- FOLD-{idx}, SAVE {args.MODEL} PREDICT ---------------')
            predicts = np.mean(kfold_predicts, axis = 0)
            if args.CLASSIFIER:
                predicts = predicts + 1
            predicts = predicts.tolist()
            # 평균 내기 전에 복구할까 평균 내고 복구할까? 일단 평균 내고 복구한다.
            submission = pd.read_csv(args.DATA_PATH + 'ratings/sample_submission.csv')
            print(f"[5-FOLD VALIDATION MEAN RMSE SCORE]: {rmse_array.mean()}")
            if args.MODEL in ('FM', 'FFM', 'NCF', 'WDN', 'DCN', 'CNN_FM', 'DeepCoNN'):
                if args.ZEROONE: # 0. ~ 1 스케일링 시
                    submission['rating'] = submission['rating'] = [p * 10 for p in predicts]
                else:
                    submission['rating'] = [p for p in predicts]
                # submission['rating'] = predicts
            else:
                pass
        
        elif args.MODEL in ('NCF', 'WDN', 'DCN'):
            for idx, (train_index, valid_index) in enumerate(skf.split(
                                                data['train'].drop(['rating'], axis = 1),
                                                data['train']['rating']
                                                )):
                data['X_train']= data['train'].drop(['rating'], axis = 1).iloc[train_index]
                data['y_train'] = data['train']['rating'].iloc[train_index]
                data['X_valid']= data['train'].drop(['rating'], axis = 1).iloc[valid_index]
                data['y_valid'] = data['train']['rating'].iloc[valid_index]
                scaler = StandardScaler()
                scaler.build(data['y_train'])
                data['y_train'] = scaler.normalize(data['y_train'])
                data['y_valid'] = scaler.normalize(data['y_valid'])
                data['scaler'] = scaler
                # print(data['X_train'].sample(5))
                data = dl_data_loader(args, data)

                print(f'--------------- FOLD-{idx}, INIT {args.MODEL} ---------------')
                if args.MODEL=='NCF':
                    model = NeuralCollaborativeFiltering(args, data)
                elif args.MODEL=='WDN':
                    model = WideAndDeepModel(args, data)
                elif args.MODEL=='DCN':
                    model = DeepCrossNetworkModel(args, data)
                
                print(f'--------------- FOLD-{idx}, {args.MODEL} TRAINING ---------------')
                rmse_score = model.train(fold_num = idx)
                rmse_array[idx] = rmse_score
                
                print(f'--------------- FOLD-{idx}, {args.MODEL} PREDICT ---------------')
                prediction = np.array(model.predict(data['test_dataloader']))
                if args.SCALER:
                    prediction = prediction * scaler.train_std + scaler.train_mean
                kfold_predicts[idx] = prediction
            
            print(f'--------------- FOLD-{idx}, SAVE {args.MODEL} PREDICT ---------------')
            predicts = np.mean(kfold_predicts, axis = 0)

            if args.CLASSIFIER:
                predicts = predicts + 1

            predicts = predicts.tolist()
            submission = pd.read_csv(args.DATA_PATH + 'ratings/sample_submission.csv')
            print(f"[5-FOLD VALIDATION MEAN RMSE SCORE]: {rmse_array.mean()}")
            if args.MODEL in ('FM', 'FFM', 'NCF', 'WDN', 'DCN', 'CNN_FM', 'DeepCoNN', 'XGB', 'LGBM', 'CATB'):
                if args.ZEROONE: # 0. ~ 1 스케일링 시
                    submission['rating'] = [p * 10 for p in predicts]
                else:
                    submission['rating'] = [p for p in predicts]
            else:
                pass
        
        elif args.MODEL == 'CNN_FM':
            for idx, (train_index, valid_index) in enumerate(skf.split(
                                                data['img_train'][['user_id', 'isbn', 'img_vector']],
                                                data['img_train']['rating']
                                                )):
                data['X_train']= data['img_train'][['user_id', 'isbn', 'img_vector']].iloc[train_index]
                data['y_train'] = data['img_train']['rating'].iloc[train_index]
                data['X_valid']= data['img_train'][['user_id', 'isbn', 'img_vector']].iloc[valid_index]
                data['y_valid'] = data['img_train']['rating'].iloc[valid_index]
                data = image_data_loader(args, data)
                scaler = data['scaler']

                print(f'--------------- FOLD-{idx}, INIT {args.MODEL} ---------------')
                model = CNN_FM(args, data)
                
                print(f'--------------- FOLD-{idx}, {args.MODEL} TRAINING ---------------')
                model.train(fold_num = idx)
                
                print(f'--------------- FOLD-{idx}, {args.MODEL} PREDICT ---------------')
                prediction = np.array(model.predict(data['test_dataloader']))
                if args.SCALER:
                    prediction = prediction * scaler.train_std + scaler.train_mean
                kfold_predicts[idx] = prediction
            
            print(f'--------------- FOLD-{idx}, SAVE {args.MODEL} PREDICT ---------------')
            predicts = np.mean(kfold_predicts, axis = 0)
            if args.CLASSIFIER:
                predicts = predicts + 1
            
            predicts = predicts.tolist()
            submission = pd.read_csv(args.DATA_PATH + 'ratings/sample_submission.csv')
            if args.MODEL in ('FM', 'FFM', 'NCF', 'WDN', 'DCN', 'CNN_FM', 'DeepCoNN', 'XGB', 'LGBM', 'CATB'):
                submission['rating'] = predicts
            else:
                pass
        
        elif args.MODEL == 'DeepCoNN':
            for idx, (train_index, valid_index) in enumerate(skf.split(
                                                data['text_train'].drop(['rating'], axis=1),
                                                data['text_train']['rating']
                                                )):
                data['X_train']= data['text_train'][data['columns'] + ['user_summary_merge_vector', 'item_summary_vector'] + ['item_title_vector', 'item_image_vector']].iloc[train_index]
                data['y_train'] = data['text_train']['rating'].iloc[train_index]
                data['X_valid']= data['text_train'][data['columns'] + ['user_summary_merge_vector', 'item_summary_vector']+ ['item_title_vector', 'item_image_vector']].iloc[valid_index]
                data['y_valid'] = data['text_train']['rating'].iloc[valid_index]
                scaler = StandardScaler()
                scaler.build(data['y_train'])
                data['y_train'] = scaler.normalize(data['y_train'])
                data['y_valid'] = scaler.normalize(data['y_valid'])
                data['scaler'] = scaler
                data = text_data_loader(args, data)

                print(f'--------------- FOLD-{idx}, INIT {args.MODEL} ---------------')
                model = DeepCoNN(args, data)
                
                print(f'--------------- FOLD-{idx}, {args.MODEL} TRAINING ---------------')
                model.train(fold_num = idx)
                
                print(f'--------------- FOLD-{idx}, {args.MODEL} PREDICT ---------------')
                prediction = np.array(model.predict(data['test_dataloader']))
                if args.SCALER:
                    prediction = prediction * scaler.train_std + scaler.train_mean
                kfold_predicts[idx] = prediction
            
            print(f'--------------- FOLD-{idx}, SAVE {args.MODEL} PREDICT ---------------')
            predicts = np.mean(kfold_predicts, axis = 0)
            if args.CLASSIFIER:
                predicts = predicts + 1
            predicts = predicts.tolist()
            submission = pd.read_csv(args.DATA_PATH + 'ratings/sample_submission.csv')
            if args.MODEL in ('FM', 'FFM', 'NCF', 'WDN', 'DCN', 'CNN_FM', 'DeepCoNN', 'XGB', 'LGBM', 'CATB'):
                submission['rating'] = predicts
            else:
                pass

                    

    now = time.localtime()
    now_date = time.strftime('%Y%m%d', now)
    now_hour = int(time.strftime('%X', now).replace(':', '')) + 90000
    if now_hour >= 240000:
        now_hour -= 240000
        if len(str(now_hour)) <= 5:
            n = 6 - len(str(now_hour))
            now_hour = '0'*n + str(now_hour)
    else:
        now_hour = str(now_hour)
    save_time = now_date + '_' + now_hour[:4]
    
    print(f"[SUBMISSION NAME] {save_time}_{args.MODEL} @@@@")
    if args.ROUND: # 라운드 된 것 안된 것 둘다 저장하기.
        submission_r = submission.copy()
        submission_r['rating'] = submission_r['rating'].apply(np.round)
        submission_r.to_csv('/opt/ml/data/submit/{}_{}_r.csv'.format(save_time, args.MODEL),index=False)
    submission.to_csv('/opt/ml/data/submit/{}_{}.csv'.format(save_time, args.MODEL), index=False)



if __name__ == "__main__":

    ######################## BASIC ENVIRONMENT SETUP
    parser = argparse.ArgumentParser(description='parser')
    arg = parser.add_argument

    ############### BASIC OPTION
    arg('--DATA_PATH', type=str, default='/opt/ml/data/', help='Data path를 설정할 수 있습니다.')
    arg('--SAVE_PATH', type = str, default = '/opt/ml/weights/', help = "학습된 모델들이 저장되는 path입니다.")
    arg('--USER_NUM', type = int, help = "user data preprocessed number `1 ~ 9`")
    arg('--BOOK_NUM', type = int, help = "book data preprocessed number `1 ~ 24`")
    arg('--CF_MODEL', default = None)
    arg('--MODEL', type=str, choices=['FM', 'FFM', 'NCF', 'WDN', 'DCN', 'CNN_FM', 'DeepCoNN', 'XGB', 'LGBM', 'CATB'],
                                help='학습 및 예측할 모델을 선택할 수 있습니다.')
    arg('--DATA_SHUFFLE', type=bool, default=True, help='데이터 셔플 여부를 조정할 수 있습니다.')
    arg('--TEST_SIZE', type=float, default=0.2, help='Train/Valid split 비율을 조정할 수 있습니다.')
    arg('--SEED', type=int, default=42, help='seed 값을 조정할 수 있습니다.')
    arg('--VALID', type = str, default = 'kfold', help = "kfold, random")
    arg('--N_SPLITS', type = int, default = 5)
    arg('--WEIGHTED_SAMPLER', type = bool, default = False)
    arg('--CLASSIFIER', type = bool, default = False)
    arg('--SCALER', type = bool, default = False)
    
    ############### TRAINING OPTION
    arg('--BATCH_SIZE', type=int, default=64, help='Batch size를 조정할 수 있습니다.')
    arg('--EPOCHS', type=int, default=50, help='Epoch 수를 조정할 수 있습니다.')
    arg('--LR', type=float, default=1e-4, help='Learning Rate를 조정할 수 있습니다.')
    arg('--WEIGHT_DECAY', type=float, default=1e-5, help='Adam optimizer에서 정규화에 사용하는 값을 조정할 수 있습니다.')
    arg('--PATIENCE', type = int, default = 3, help = 'Early Stop patience')
    arg('--ZEROONE', type=bool, default=False, help = '0. ~ 1 스케일링 합니다.')
    arg('--ROUND', type=bool, default=False, help = '점수 반올림 진행합니다.')
    arg('--OPTIM', type=str, default='adam', help='Optimizer를 adam과 sgd 중에서 골라주세요')
    arg('--SCHEDULER', type=str, default=None, help='Learning Scheduler를 적용할 수 있습니다.(steplr)')

    ############### Loss Func
    arg('--LOSS', type=str, default='rmse', help='rmse, sl1, huber')
    arg('--BETA', type=float, default=1.0, help='smooth l1, hubor 에서 베타, 델타 지정합니다.(0 ~ 1)')


    ############### GPU
    arg('--DEVICE', type=str, default='cuda', choices=['cuda', 'cpu'], help='학습에 사용할 Device를 조정할 수 있습니다.')

    ############### FM
    arg('--FM_EMBED_DIM', type=int, default=16, help='FM에서 embedding시킬 차원을 조정할 수 있습니다.')

    ############### FFM
    arg('--FFM_EMBED_DIM', type=int, default=16, help='FFM에서 embedding시킬 차원을 조정할 수 있습니다.')

    ############### NCF
    arg('--NCF_EMBED_DIM', type=int, default=16, help='NCF에서 embedding시킬 차원을 조정할 수 있습니다.')
    arg('--NCF_MLP_DIMS', type=list, default=(16, 16), help='NCF에서 MLP Network의 차원을 조정할 수 있습니다.')
    arg('--NCF_DROPOUT', type=float, default=0.2, help='NCF에서 Dropout rate를 조정할 수 있습니다.')

    ############### WDN
    arg('--WDN_EMBED_DIM', type=int, default=16, help='WDN에서 embedding시킬 차원을 조정할 수 있습니다.')
    arg('--WDN_MLP_DIMS', type=list, default=(16, 16), help='WDN에서 MLP Network의 차원을 조정할 수 있습니다.')
    arg('--WDN_DROPOUT', type=float, default=0.2, help='WDN에서 Dropout rate를 조정할 수 있습니다.')

    ############### DCN
    arg('--DCN_EMBED_DIM', type=int, default=16, help='DCN에서 embedding시킬 차원을 조정할 수 있습니다.')
    arg('--DCN_MLP_DIMS', type=list, default=(16, 16), help='DCN에서 MLP Network의 차원을 조정할 수 있습니다.')
    arg('--DCN_DROPOUT', type=float, default=0.2, help='DCN에서 Dropout rate를 조정할 수 있습니다.')
    arg('--DCN_NUM_LAYERS', type=int, default=3, help='DCN에서 Cross Network의 레이어 수를 조정할 수 있습니다.')

    ############### CNN_FM
    arg('--CNN_FM_EMBED_DIM', type=int, default=128, help='CNN_FM에서 user와 item에 대한 embedding시킬 차원을 조정할 수 있습니다.')
    arg('--CNN_FM_LATENT_DIM', type=int, default=8, help='CNN_FM에서 user/item/image에 대한 latent 차원을 조정할 수 있습니다.')

    ############### DeepCoNN
    arg('--DEEPCONN_VECTOR_CREATE', type=bool, default=False, help='DEEP_CONN에서 text vector 생성 여부를 조정할 수 있으며 최초 학습에만 True로 설정하여야합니다.')
    arg('--DEEPCONN_EMBED_DIM', type=int, default=32, help='DEEP_CONN에서 user와 item에 대한 embedding시킬 차원을 조정할 수 있습니다.')
    arg('--DEEPCONN_LATENT_DIM', type=int, default=10, help='DEEP_CONN에서 user/item/image에 대한 latent 차원을 조정할 수 있습니다.')
    arg('--DEEPCONN_CONV_1D_OUT_DIM', type=int, default=50, help='DEEP_CONN에서 1D conv의 출력 크기를 조정할 수 있습니다.')
    arg('--DEEPCONN_KERNEL_SIZE', type=int, default=3, help='DEEP_CONN에서 1D conv의 kernel 크기를 조정할 수 있습니다.')
    arg('--DEEPCONN_WORD_DIM', type=int, default=512, help='DEEP_CONN에서 1D conv의 입력 크기를 조정할 수 있습니다.')
    arg('--DEEPCONN_OUT_DIM', type=int, default=32, help='DEEP_CONN에서 1D conv의 출력 크기를 조정할 수 있습니다.')


    ############### XGBoost
    arg('--XGB_RR_CL', type=str, default='rr', help='XGB regression(rr), classifier(cl) 중 선택합니다.')
    arg('--XGB_MAX_DEPTH', type=int, default=6, help='XGB에서 트리 깊이 지정하며 깊을수록 복잡한 모델이 됩니다.')


    ############### LightGBM
    arg('--LGBM_RR_CL', type=str, default='rr', help='LGBM regression(rr), classifier(cl) 중 선택합니다. 기본 rr.')
    
    ############### CatBoost
    arg('--CATB_RR_CL', type=str, default='rr', help='CATB regression(rr), classifier(cl) 중 선택합니다. 기본 rr.')
    

    args = parser.parse_args()
    main(args)
