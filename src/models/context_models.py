import tqdm
import os
import numpy as np

import torch
import torch.nn as nn
import torch.optim as optim

from ._models import _FactorizationMachineModel, _FieldAwareFactorizationMachineModel
from ._models import rmse, acc, confusion_mat, RMSELoss, SmoothL1Loss, CrossEntropyLoss
from src.utils import EarlyStopping

class FactorizationMachineModel:

    def __init__(self, args, data, cf=False):
        super().__init__()
        self.args = args
        ## 클래시파이어로 변환하는 과정 및 로스 교체 코드
        self.cf = cf
        if cf:
            last_dim = len(data['ranges'])
            weight = torch.FloatTensor([0.43, 0.27, 0.35]).to(args.DEVICE)
            print('Loss: CrossEntropyLoss')
            self.criterion = CrossEntropyLoss(weight=weight)
        else:
            last_dim = 1
            if args.LOSS == 'sl1':
                print('Loss: sl1')
                self.criterion = SmoothL1Loss(self.args.BETA)
            elif args.LOSS == 'rmse':
                print('Loss: rmse')
                self.criterion = RMSELoss()

        self.train_dataloader = data['train_dataloader']
        self.valid_dataloader = data['valid_dataloader']
        self.field_dims = data['field_dims']

        self.embed_dim = args.FM_EMBED_DIM
        self.epochs = args.EPOCHS
        ## 리그레션 일 시 클래시파이어 일시 달라짐
        # if cf:
        #     self.learning_rate = args.CF_LR
        # else:
        #     self.learning_rate = args.RR_LR

        self.learning_rate = args.LR
        self.weight_decay = args.WEIGHT_DECAY
        self.log_interval = 100

        self.device = args.DEVICE

        self.model = _FactorizationMachineModel(self.field_dims, self.embed_dim, last_dim=last_dim).to(self.device)
        self.optimizer = torch.optim.Adam(params=self.model.parameters(), lr=self.learning_rate, amsgrad=True, weight_decay=self.weight_decay)


    def train(self, fold_num):
      # model: type, optimizer: torch.optim, train_dataloader: DataLoader, criterion: torch.nn, device: str, log_interval: int=100
        early_stopping = EarlyStopping(args=self.args, fold_num = fold_num, verbose=True)
        for epoch in range(self.epochs):
            self.model.train()
            total_loss = 0
            tk0 = tqdm.tqdm(self.train_dataloader, smoothing=0, mininterval=1.0)
            for i, (fields, target) in enumerate(tk0):
                self.model.zero_grad()
                fields, target = fields.to(self.device), target.to(self.device)

                y = self.model(fields)

                # 클래시파이어 부분
                if self.cf:
                    loss = self.criterion(y, target.long())
                else:
                    loss = self.criterion(y, target.float())

                loss.backward()
                self.optimizer.step()
                total_loss += loss.item()
                if (i + 1) % self.log_interval == 0:
                    tk0.set_postfix(loss=total_loss / self.log_interval)
                    total_loss = 0

            rmse_score = self.predict_train()
            early_stopping(rmse_score, self.model)  

            if early_stopping.early_stop:
                print("Early stopping")
                break

        formatted_user_num = format(self.args.USER_NUM, '02')
        formatted_book_num = format(self.args.BOOK_NUM, '02')
        ppath = os.path.join(self.args.SAVE_PATH,
            self.args.MODEL, ## 클래시파이어 수정 부분
            f"u{formatted_user_num}_b{formatted_book_num}",
            f"fold{fold_num}",
            'checkpoint.pt')
        self.model.load_state_dict(torch.load(ppath))
        rmse_score = self.predict_train()
        print(f"u{formatted_user_num}_b{formatted_book_num}, validation rmse: {rmse_score}")
        print('\n')
        return rmse_score



    def predict_train(self):
        self.model.eval()
        targets, predicts = list(), list()
        with torch.no_grad():
            for fields, target in tqdm.tqdm(self.valid_dataloader, smoothing=0, mininterval=1.0):
                fields, target = fields.to(self.device), target.to(self.device)
                y = self.model(fields)
                targets.extend(target.tolist())
                predicts.extend(y.tolist())

        if self.cf:
            # print(np.argmax(predicts, axis=1), targets)
            t = np.get_printoptions()
            np.set_printoptions(precision=2)

            print('[confusion matrix] row: real, col: pred\n', confusion_mat(targets, np.argmax(predicts, axis=1)) * 100)
            print('[classification acc]:', f'{acc(targets, np.argmax(predicts, axis=1)) * 100:.3f}%')
            np.set_printoptions(precision=t['precision'])

            return rmse(targets, np.argmax(predicts, axis=1))

        if self.args.ZEROONE:
            return rmse([t * 10.0 for t in targets], [p * 10.0 for p in predicts])
        else:
            return rmse(targets, predicts)


    def predict(self, dataloader):
        self.model.eval()
        predicts = list()
        with torch.no_grad():
            for fields in tqdm.tqdm(dataloader, smoothing=0, mininterval=1.0):
                fields = fields[0].to(self.device)
                y = self.model(fields)
                predicts.extend(y.tolist())

        # 클래시파이어 부분
        if self.cf:
            return np.argmax(predicts, axis=1)
        return predicts


class FieldAwareFactorizationMachineModel:

    def __init__(self, args, data):
        super().__init__()
        self.args = args
        self.criterion = RMSELoss()

        self.train_dataloader = data['train_dataloader']
        self.valid_dataloader = data['valid_dataloader']
        self.field_dims = data['field_dims']

        self.embed_dim = args.FFM_EMBED_DIM
        self.epochs = args.EPOCHS
        self.learning_rate = args.LR
        self.weight_decay = args.WEIGHT_DECAY
        self.log_interval = 100

        self.device = args.DEVICE

        self.model = _FieldAwareFactorizationMachineModel(self.field_dims, self.embed_dim).to(self.device)
        self.optimizer = torch.optim.Adam(params=self.model.parameters(), lr=self.learning_rate, amsgrad=True, weight_decay=self.weight_decay)


    def train(self, fold_num):
      # model: type, optimizer: torch.optim, train_dataloader: DataLoader, criterion: torch.nn, device: str, log_interval: int=100
        early_stopping = EarlyStopping(args=self.args, fold_num = fold_num, verbose=True)

        for epoch in range(self.epochs):
            self.model.train()
            total_loss = 0
            tk0 = tqdm.tqdm(self.train_dataloader, smoothing=0, mininterval=1.0)
            for i, (fields, target) in enumerate(tk0):
                fields, target = fields.to(self.device), target.to(self.device)
                y = self.model(fields)
                loss = self.criterion(y, target.float())
                self.model.zero_grad()
                loss.backward()
                self.optimizer.step()
                total_loss += loss.item()
                if (i + 1) % self.log_interval == 0:
                    tk0.set_postfix(loss=total_loss / self.log_interval)
                    total_loss = 0
            
            rmse_score = self.predict_train()
            early_stopping(rmse_score, self.model)

            if early_stopping.early_stop:
                print("Early stopping")
                break
        formatted_user_num = format(self.args.USER_NUM, '02')
        formatted_book_num = format(self.args.BOOK_NUM, '02')
        ppath = os.path.join(self.args.SAVE_PATH,
            self.args.MODEL,
            f"u{formatted_user_num}_b{formatted_book_num}",
            f"fold{fold_num}",
            'checkpoint.pt')
        self.model.load_state_dict(torch.load(ppath))
        rmse_score = self.predict_train()
        print(f"u{formatted_user_num}_b{formatted_book_num}, validation rmse: {rmse_score}")
        print('\n')
        return rmse_score


    def predict_train(self):
        self.model.eval()
        targets, predicts = list(), list()
        with torch.no_grad():
            for fields, target in tqdm.tqdm(self.valid_dataloader, smoothing=0, mininterval=1.0):
                fields, target = fields.to(self.device), target.to(self.device)
                y = self.model(fields)
                targets.extend(target.tolist())
                predicts.extend(y.tolist())
        if self.args.ZEROONE:
            return rmse([t * 10.0 for t in targets], [p * 10.0 for p in predicts])
        else:
            return rmse(targets, predicts)


    def predict(self, dataloader):
        self.model.eval()
        predicts = list()
        with torch.no_grad():
            for fields in tqdm.tqdm(dataloader, smoothing=0, mininterval=1.0):
                fields = fields[0].to(self.device)
                y = self.model(fields)
                predicts.extend(y.tolist())
        return predicts
