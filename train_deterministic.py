from __future__ import print_function

import os
import sys
sys.dont_write_bytecode=True

import warnings
warnings.filterwarnings("ignore")

import glob
import numpy as np 
import random

import torch

from torch.utils.data import DataLoader
from arguments import parse_arguments
from model import TrajectoryGenerator
from data import dataset, collate_function

from utils import * 

args = parse_arguments()
print(args.__dict__)
seed = 10
random.seed(seed)
torch.manual_seed(seed)
torch.cuda.manual_seed(seed)
np.random.seed(seed)
torch.initial_seed()


torch.set_printoptions(precision=2)

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
if torch.cuda.is_available():
	gpu_id = get_free_gpu().item()
	torch.cuda.set_device(gpu_id)

if not args.test_only:
	print("TRAINING DATA")
	traindataset = dataset(glob.glob(f"data/{args.dset_name}/train/*.txt"), args)
	print(f"Number of Training Samples: {len(traindataset)}")
	print("VALIDATION DATA")
	valdataset = dataset(glob.glob(f"data/{args.dset_name}/val/*.txt"), args)
	print(f" Number of Validation Samples: {len(valdataset)}")

print("TEST DATA")
testdataset = dataset(glob.glob(f"data/{args.dset_name}/test/*.txt"), args)
print(f"Number of Test Samples: {len(testdataset)}")

print("-"*100)

if not args.test_only:
	trainloader = DataLoader(traindataset, batch_size=args.batch_size, collate_fn=collate_function(),  shuffle=True)
	validloader = DataLoader(valdataset, batch_size=args.eval_batch_size if not args.eval_batch_size is None else len(valdataset), collate_fn=collate_function(),  shuffle=False)
	testloader = DataLoader(testdataset, batch_size=args.eval_batch_size if not args.eval_batch_size is None else len(testdataset), collate_fn=collate_function(),  shuffle=False)

model = TrajectoryGenerator(model_type=args.model_type, obs_len=args.obs_len, pred_len=args.pred_len, feature_dim=2, embedding_dim=args.embedding_dim, encoder_dim=args.encoder_dim, decoder_dim=args.decoder_dim, attention_dim=args.attention_dim, domain_parameter=args.domain_parameter, delta_bearing=args.delta_bearing, delta_heading=args.delta_heading, pretrained_scene="resnet18", device=device, noise_dim=None, noise_type=None).float().to(device)

model.apply(init_weights)

optimizer = torch.optim.Adam(model.parameters(), lr=args.lr) 
if args.scheduler:
	scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, threshold=0.01, patience=10, factor=0.5, verbose=True, min_lr=1e-04)

best_loss=float(np.inf)

model_file = f"./trained-models/{args.model_type}/{args.dset_name}"

if not os.path.exists(f"./trained-models/{args.model_type}"): 
	print(f"Creating directory ./trained-models/{args.model_type}")
	os.makedirs(f"./trained-models/{args.model_type}")

if args.train_saved:
	model.load_state_dict(torch.load(f"{model_file}.pt", map_location=device))

if args.test_only:
	print("Evaluating trained model")
	model.load_state_dict(torch.load(f"{model_file}.pt", map_location=device))
	testloader = DataLoader(testdataset, batch_size=args.eval_batch_size, collate_fn=collate_function(),  shuffle=False)
	test_ade, test_fde = evaluate_model(model, testloader)
	print(f"Test ADE: {test_ade:.3f}")
	print(f"Test FDE: {test_fde:.3f}")
	
	exit()

print("TRAINING")

for epoch in range(args.num_epochs):
	epoch_ade = float(0)
	model.train()
	for b, batch in enumerate(trainloader):
		optimizer.zero_grad()
		pred, target, sequence, pedestrians, op_mask, ip_mask = predict(batch, model)
		ade_b, fde_b = eval_metrics(pred, target, pedestrians, op_mask)
		ade_b.backward()
		optimizer.step()
		epoch_ade+=ade_b.item()
	epoch_ade/=(b+1)
	print(f"EPOCH: {epoch+1} Train ADE: {epoch_ade:.3f}")
	model.eval()
	val_ade, valid_fde = evaluate_model(model, validloader)
	if args.scheduler:
		scheduler.step(val_ade)
	if (val_ade<best_loss):
		best_loss=val_ade 
		torch.save(model.state_dict(), f"{model_file}.pt")
		test_ade, test_fde = evaluate_model(model, testloader)
	print(f"Valid ADE: {val_ade:.3f}\nTest ADE: {test_ade:.3f} Test FDE: {test_fde:.3f}")  
	print("*"*50)

print("Finished Training")

model.eval()

print("Evaluating trained model")
model.load_state_dict(torch.load(f"{model_file}.pt"))
testloader = DataLoader(testdataset, batch_size=args.eval_batch_size, collate_fn=collate_function(),  shuffle=False)
test_ade, test_fde = evaluate_model(model, testloader)
print(f"Test ADE: {test_ade:.3f}")
print(f"Test FDE: {test_fde:.3f}")





    
        


