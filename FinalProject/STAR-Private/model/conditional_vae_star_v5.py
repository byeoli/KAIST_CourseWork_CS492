''' This code contains the implementation of conditional VAE
https://github.com/graviraja/pytorch-sample-codes/blob/master/conditional_vae.py
'''

#https://github.com/pytorch/pytorch/issues/9158
import os
os.environ["CUDA_DEVICE_ORDER"]="PCI_BUS_ID"
os.environ["CUDA_VISIBLE_DEVICES"] = "2,3,4"

import sys
import time
import datetime
import wandb
import numpy as np

import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
import torch.optim.lr_scheduler
from torchvision import datasets, transforms
from torch.utils.data import DataLoader
#https://greeksharifa.github.io/references/2020/06/10/wandb-usage/
from torch.nn.parallel.data_parallel import DataParallel

sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))
from utils.datasets_v5 import StarBetaBoneLengthDataset, Normalize
import model_v5 as md
from demo.load_chumpy import extract_obj, save_as_obj


class PathControllTower:
    def __init__(self, root) -> None:
        self.root = root

    def get_train_data(self):
        return self.root + 'train.npz'

    def get_test_data(self):
        return self.root + 'test.npz'

    def get_validation_data(self):
        return self.root + 'validation.npz'

    def get_reference_data(self):
        return self.root + 'reference.npz'

####################################################################
# Set up your default hyperparameters before wandb.init
# so they get properly set in the sweep
# last channel is always (hidden_dim, target_dim) not follow config.
device = 'cuda' if torch.cuda.is_available() else 'cpu'
e = 0
task = 'train'
####################################################################
# ROOT = (os.path.dirname(os.path.realpath(__file__)))
STARPATH = PathControllTower(root='./data/')
SMPLPATH = PathControllTower(root='C:/Users/Choi Byeoli/STAR-Private/datasmpl/')
DATAPATH = SMPLPATH
GPU_VISIBLE_NUM = os.environ["CUDA_VISIBLE_DEVICES"].count(',') + 1

TIMEPATH = None
TIMEPATH = '2021_06_05_16_59_22_99'
tm = time.localtime()
TRAINED_TIME = time.strftime('%Y_%m_%d_%H_%M_%S', tm)
####################################################################
# TRAIN_SIZE = 64
# TEST_SIZE = 64
TRAIN_SIZE = 2048
TEST_SIZE = 64
BATCH_SIZE = 32         # number of data points in each batch
N_EPOCHS = 100           # times to run the model on complete data
lr = 1e-2               # learning rate
####################################################################

loss_prev = 0.1
loss_current = 0.0

####################################################################
def _save(func, args, path):
    temp = path.split(os.path.sep)
    dirpath = path[:-(len(temp[-1])+1)]
    os.makedirs(dirpath, exist_ok=True)
    func(*args)

def _getfloat(value, attr='item'):
    if hasattr(value, attr):
        return value.item()
    else:
        return value

def weight_interpolate(factor, target_network, network):
    for target_param, param in zip(target_network.parameters(), network.parameters()):
        target_param.data.copy_(param.data * factor + target_param.data*(1.0 - factor))


def weight_add(percent, target_network, network):
    for target_param, param in zip(target_network.parameters(), network.parameters()):
        target_param.data.copy_(param.data * percent + target_param.data)


def weight_self_divide(percent, target_network):
    for target_param in target_network.parameters():
        target_param.data.copy_(target_param.data * percent)


def train(model,model_jacobian,model_temp,train_iterator,optimizer,optimizer_jacobian):
    global generated_beta_list, generated_bonelength_list, task
    task = 'train'
    # set the train mode
    model.train()
    model_jacobian.train()

    # loss of the epoch
    train_loss = 0
    losses = {'KLD':0.0,'RCL_bone':0.0,'RCL_x':0.0,'Cov':0.0,'Jac':0.0,'RCL_x_euclidean_distance':0.0}
    training_bias = (TRAIN_SIZE - 1) / (BATCH_SIZE - 1)
    
    optimizer.zero_grad()
    optimizer_jacobian.zero_grad()

    #TODO:fix it -> parallel gpu 사용시 할당되는 .to(device)를 조절해야하므로 constant 참고값도 불러온다
    for i, (beta, shapeblendshape, mesh_shape_pos, jointregressor_matrix) in enumerate(train_iterator):
        print(i)
        beta = beta.to(device)
        shapeblendshape = shapeblendshape.to(device)
        mesh_shape_pos = mesh_shape_pos.to(device)
        jointregressor_matrix = jointregressor_matrix.to(device)
        weight_interpolate(1.0, model_temp, model)
        weight_interpolate(1.0, model_jacobian, model)

        # forward pass
        # loss
        output = model(beta=beta,
                        shapeblendshape=shapeblendshape, 
                        mesh_shape_pos=mesh_shape_pos, 
                        jointregressor_matrix=jointregressor_matrix)
        
        generated_beta, generated_bonelength, mu_Style, std_Style, bonelength_reduced, mesh, generated_mesh, z_Style, bonelength = output

        if e == N_EPOCHS-1 and i == 0:
            generated_beta_list += [[beta, generated_beta]]
            generated_bonelength_list += [[bonelength, generated_bonelength]]
            
        loss_func_basic = md.loss_func_basic(model=model,
                                X=mesh, X_hat=generated_mesh,
                                bonelength=bonelength, generated_bonelength=generated_bonelength,
                                mu_S=mu_Style, std_S=std_Style,
                                mu_B=bonelength_reduced, beta=beta,
                                generated_beta=generated_beta,
                                training_bias=training_bias,
                                BATCH_SIZE=BATCH_SIZE, device=device)

        loss_a, sublosses, L_covarpen = loss_func_basic
        
        # backward pass
        loss_a.backward()
        train_loss += _getfloat(loss_a)

        losses['KLD'] += _getfloat(sublosses['KLD'])
        losses['RCL_bone'] += _getfloat(sublosses['RCL_bone'])
        losses['RCL_x'] += _getfloat(sublosses['RCL_x'])
        losses['RCL_x_euclidean_distance'] += _getfloat(sublosses['RCL_x_euclidean_distance'])
        losses['Cov'] += _getfloat(L_covarpen)

        # update the weights
        optimizer.step()

        # update the gradients to zero
        optimizer.zero_grad()

    train_loss =  train_loss
    return train_loss, losses


def test(model,model_jacobian,test_iterator,IsNeedSave=False):
    global generated_beta_list, generated_bonelength_list, task
    task = 'test'
    # set the evaluation mode
    model.eval()

    # test loss for the data
    test_loss = 0
    losses = {'KLD':0.0,'RCL_bone':0.0,'RCL_x':0.0,'Cov':0.0,'Jac':0.0,'RCL_x_euclidean_distance':0.0}
    training_bias = (TEST_SIZE - 1) / (BATCH_SIZE - 1)

    # we don't need to track the gradients, since we are not updating the parameters during evaluation / testing
    with torch.no_grad():
        weight_interpolate(1.0, model_jacobian, model)
        for i, (beta, shapeblendshape, mesh_shape_pos, jointregressor_matrix) in enumerate(test_iterator):
            beta = beta.to(device)
            shapeblendshape = shapeblendshape.to(device)
            mesh_shape_pos = mesh_shape_pos.to(device)
            jointregressor_matrix = jointregressor_matrix.to(device)

            
            output = model(beta=beta,
                            shapeblendshape=shapeblendshape, 
                            mesh_shape_pos=mesh_shape_pos, 
                            jointregressor_matrix=jointregressor_matrix)

            generated_beta, generated_bonelength, mu_Style, std_Style, bonelength_reduced, mesh, generated_mesh, z_Style, bonelength = output

            if i == 0 and IsNeedSave:
                generated_beta_list += [[beta, generated_beta]]
                generated_bonelength_list += [[bonelength, generated_bonelength]]

            loss_func_basic = md.loss_func_basic(model=model,
                                    X=mesh, X_hat=generated_mesh,
                                    bonelength=bonelength, generated_bonelength=generated_bonelength,
                                    mu_S=mu_Style, std_S=std_Style,
                                    mu_B=bonelength_reduced, beta=beta,
                                    generated_beta=generated_beta,
                                    training_bias=training_bias,
                                    BATCH_SIZE=BATCH_SIZE, device=device)
            
            loss_a, sublosses, L_covarpen = loss_func_basic
            
            test_loss += _getfloat(loss_a)

            losses['KLD'] += _getfloat(sublosses['KLD'])
            losses['RCL_bone'] += _getfloat(sublosses['RCL_bone'])
            losses['RCL_x'] += _getfloat(sublosses['RCL_x'])
            losses['RCL_x_euclidean_distance'] += _getfloat(sublosses['RCL_x_euclidean_distance'])
            losses['Cov'] += _getfloat(L_covarpen)

            for k in range(BATCH_SIZE):
                save_as_obj(model=mesh[0].cpu().data.numpy(),save_path="C:/Users/Choi Byeoli/STAR-Private/outputs/",name=TRAINED_TIME+"_" + str(k + BATCH_SIZE * i).zfill(4) + "_before")
                save_as_obj(model=generated_mesh[0].cpu().data.numpy(),save_path="C:/Users/Choi Byeoli/STAR-Private/outputs/",name=TRAINED_TIME+"_" + str(k + BATCH_SIZE * i).zfill(4) + "_after")
    test_loss =  test_loss
    return test_loss, losses

def load_trained_model(model, model_jacobian, _dataset, _iterator):
    checkpoint = torch.load(TIMEPATH + '.pt')
    model.load_state_dict(checkpoint['model_state_dict'])
    epoch = checkpoint['epoch']
    num_batch = float(len(_dataset))/float(BATCH_SIZE)

    e = epoch

    test_loss, test_losses = test(model, model_jacobian, _iterator, IsNeedSave=True)
    
    test_loss /= num_batch

    
    metrics = { 'loss': test_loss,
                'Jac': test_losses['Jac']/num_batch,
                'KLD': test_losses['KLD']/num_batch,
                'RCL_bone': test_losses['RCL_bone']/num_batch,
                'RCL_x': test_losses['RCL_x']/num_batch,
                'RCL_x_euclidean_distance': test_losses['RCL_x_euclidean_distance']/num_batch,
                'Cov': test_losses['Cov']/num_batch,
                }
    wandb.log(metrics)

    print(f'Epoch {e}, The Loss: {test_loss:.4f}')

def save_trained_model(model, model_jacobian, model_temp,train_dataset, test_dataset, train_iterator, test_iterator, optimizer, optimizer_jacobian, scheduler, scheduler_jacobian):
    global e, loss_prev,loss_current
    e = 0

    for e in range(N_EPOCHS):
        train_loss, train_losses = train(model, model_jacobian, model_temp, train_iterator, optimizer, optimizer_jacobian)
        test_loss, test_losses = test(model, model_jacobian, test_iterator)
        num_batch_train = float(len(train_dataset))/float(BATCH_SIZE)
        num_batch_test = float(len(test_dataset))/float(BATCH_SIZE)

        train_loss /= num_batch_train
        test_loss /= num_batch_test


        metrics = {'train_loss': train_loss, 
                    'test_loss': test_loss,
                    'train_Jac': train_losses['Jac']/num_batch_train,
                    'test_Jac': test_losses['Jac']/num_batch_test,
                    'train_KLD': train_losses['KLD']/num_batch_train,
                    'train_RCL_bone': train_losses['RCL_bone']/num_batch_train,
                    'train_RCL_x': train_losses['RCL_x']/num_batch_train,
                    'train_RCL_x_euclidean_distance': train_losses['RCL_x_euclidean_distance']/num_batch_train,
                    'train_Cov': train_losses['Cov']/num_batch_train,
                    'test_KLD': test_losses['KLD']/num_batch_test,
                    'test_RCL_bone': test_losses['RCL_bone']/num_batch_test,
                    'test_RCL_x': test_losses['RCL_x']/num_batch_test,
                    'test_RCL_x_euclidean_distance': test_losses['RCL_x_euclidean_distance']/num_batch_test,
                    'test_Cov': test_losses['Cov']/num_batch_test,
                    }
        wandb.log(metrics)

        print(f'Epoch {e}, Train Loss: {train_loss:.4f}, Test Loss: {test_loss:.4f}')

        scheduler.step()

        if e > 1 and ((e % 10 == 4) or (e % 10 == 9)):
        # https://tutorials.pytorch.kr/beginner/saving_loading_models.html
            _path = TIMEPATH + '_' +str(e) + '.pt'
        # loss_prev = loss_current
        # loss_current = train_losses['Jac']/len(train_dataset)
        # if e > 1 and loss_current > loss_prev * 100:
        #     print(f'loss_prev:{loss_prev},loss_current:{loss_current}')
        #     break
            _save(torch.save,
            args=({
                'epoch': N_EPOCHS,
                'model_state_dict': model.state_dict(),
                'optimizer_state_dict': optimizer.state_dict(),
                },_path),
            path=_path)


def wrapper():
    return setup_trained_model()


def transformation():
    mean = 0.0
    std = 5.0

    transform = transforms.Compose([
        Normalize(mean=mean, std=std),
        #ToTensor, #왜 안써야하지?
    ])

    return transform

def setup_trained_model():
    global TIMEPATH, generated_beta_list, config, TRAINED_TIME

    root = "C:/Users/Choi Byeoli/STAR-Private/outputs/weight/"

    if TIMEPATH is None:
        TIMEPATH = os.path.join(root,'cvae_' + TRAINED_TIME)
    else:
        TIMEPATH = os.path.join(root,'cvae_' + TIMEPATH)

    transform = transformation()

    train_dataset = StarBetaBoneLengthDataset(
        path_data=DATAPATH.get_train_data(),
        path_reference=DATAPATH.get_reference_data(),
        transform=transform,
        debug=TRAIN_SIZE
    )

    test_dataset = StarBetaBoneLengthDataset(
        path_data=DATAPATH.get_test_data(),
        path_reference=DATAPATH.get_reference_data(),
        transform=transform,
        debug=TEST_SIZE
    )

    validation_dataset = StarBetaBoneLengthDataset(
        path_data=DATAPATH.get_validation_data(),
        path_reference=DATAPATH.get_reference_data(),
        transform=transform,
        debug=TEST_SIZE
    )

    train_iterator = DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True, num_workers=0)
    test_iterator = DataLoader(test_dataset, batch_size=BATCH_SIZE, shuffle=False, num_workers=0)
    validation_iterator = DataLoader(validation_dataset, batch_size=BATCH_SIZE, shuffle=False, num_workers=0)

    model = md.CVAE(BATCH_SIZE=BATCH_SIZE)
    model_jacobian = md.CVAE(BATCH_SIZE=BATCH_SIZE, IsSupporter=True)
    model_temp = md.CVAE(BATCH_SIZE=BATCH_SIZE, IsSupporter=True)

    assert(GPU_VISIBLE_NUM > 1, "You need at least 2 GPUs")
    print("Let's use", GPU_VISIBLE_NUM, "GPUs!")
    # dim = 0 [30, xxx] -> [10, ...], [10, ...], [10, ...] on 3 GPUs
    model = DataParallel(model)
    model_jacobian = DataParallel(model_jacobian)
    model_temp = DataParallel(model_jacobian)

    model.to(device)
    model_jacobian.to(device)
    model_temp.to(device)


    optimizer = optim.Adam(model.parameters(), lr=lr)
    optimizer_jacobian = optim.Adam(model.parameters(), lr=lr)
    #http://www.gisdeveloper.co.kr/?p=8443
    scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=20, gamma=0.1)
    scheduler_jacobian = torch.optim.lr_scheduler.StepLR(optimizer, step_size=20, gamma=0.1)

    if not os.path.isfile(TIMEPATH + '.pt'):
        #sort, dnn style, load data, input/loss, version
        wandb.init(project="STARVAE-7-with-Cov-Jac")
        wandb.watch(model)
        save_trained_model(model, model_jacobian, model_temp, train_dataset, test_dataset, train_iterator, test_iterator, optimizer, optimizer_jacobian, scheduler, scheduler_jacobian)
    else:
        wandb.init(project="STARVAE-7-with-Cov-Jac-temp")
        wandb.watch(model)
        load_trained_model(model, model_jacobian, validation_dataset, validation_iterator)

    return model, train_iterator, test_iterator, validation_dataset

#정확히는 마지막 loss 지나고 나서 구한것
def get_obj(model, save_path, name, _beta, _iterator, IsOriginal=False):
    global BATCH_SIZE
    beta = torch.zeros((BATCH_SIZE,_beta.shape[-1]),dtype=torch.float32,device=device)
    for i in range(BATCH_SIZE):
        beta[i,:] = _beta
    
    for i, (_, shapeblendshape, mesh_shape_pos, jointregressor_matrix) in enumerate(_iterator):
        beta = _beta.to(device)
        shapeblendshape = shapeblendshape.to(device)
        mesh_shape_pos = mesh_shape_pos.to(device)
        jointregressor_matrix = jointregressor_matrix.to(device)

        output = model(beta=beta,
                        shapeblendshape=shapeblendshape, 
                        mesh_shape_pos=mesh_shape_pos, 
                        jointregressor_matrix=jointregressor_matrix)
        
        generated_beta, generated_bonelength, mu_Style, std_Style, bonelength_reduced, mesh, generated_mesh, z_Style, bonelength = output

        if IsOriginal:
            save_as_obj(model=mesh[0].cpu().data.numpy(),save_path=save_path,name=name)
        else:
            save_as_obj(model=generated_mesh[0].cpu().data.numpy(),save_path=save_path,name=name)
        break




def main():
    global generated_beta_list, generated_bonelength_list
    generated_beta_list = []
    generated_bonelength_list = []
    model, train_iterator, test_iterator, validation_dataset = wrapper()

    np.set_printoptions(precision=3, suppress=True)
    # for bone_pair in generated_bonelength_list:
    bone_pair = generated_bonelength_list[-1]
    original_val = bone_pair[0].detach().cpu().numpy()[0, :]
    new_val = bone_pair[1].detach().cpu().numpy()[0, :]
    print(f'\n\n\n\n*--------------------bone------------------*')
    print(f'original:\n{original_val}')
    print(f'new:\n{new_val}')
    print(f'divide:\n{(abs(original_val) - abs(new_val))}')
    print(f'percent:\n{(abs(original_val) - abs(new_val))/abs(original_val) * 100.0}')

    beta_pair = generated_beta_list[-1]
    original_val = beta_pair[0].detach().cpu().numpy()[0,:]
    new_val = beta_pair[1].detach().cpu().numpy()[0,:]
    print(f'\n\n\n\n*--------------------beta------------------*')
    print(f'original:\n{original_val}')
    print(f'new:\n{new_val}')
    print(f'divide:\n{(abs(original_val) - abs(new_val))}')
    print(f'percent:\n{(abs(original_val) - abs(new_val))/abs(original_val) * 100.0}')
    
    get_obj(model=model,save_path="C:/Users/Choi Byeoli/STAR-Private/outputs/",name=TRAINED_TIME+"_new",_beta=original_val,_iterator=train_iterator)
    get_obj(model=model,save_path="C:/Users/Choi Byeoli/STAR-Private/outputs/",name=TRAINED_TIME+"_new",_beta=new_val,_iterator=train_iterator)
    # extract_obj(save_path="/Data/MGY/STAR-Private/outputs/",name=TRAINED_TIME+"_original",betas=original_val)
    # extract_obj(save_path="/Data/MGY/STAR-Private/outputs/",name=TRAINED_TIME+"_new",betas=new_val)


if __name__ == "__main__":
    #https://www.studytonight.com/post/calculate-time-taken-by-a-program-to-execute-in-python
    start = time.time()
    main()
    end = time.time()
    print(f"Runtime of the program is {str(datetime.timedelta(seconds=end-start))}")
