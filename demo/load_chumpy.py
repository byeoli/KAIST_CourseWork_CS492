# -*- coding: utf-8 -*-
#
# Copyright (C) 2020 Max-Planck-Gesellschaft zur Förderung der Wissenschaften e.V. (MPG),
# acting on behalf of its Max Planck Institute for Intelligent Systems and the
# Max Planck Institute for Biological Cybernetics. All rights reserved.
#
# Max-Planck-Gesellschaft zur Förderung der Wissenschaften e.V. (MPG) is holder of all proprietary rights
# on this computer program. You can only use this computer program if you have closed a license agreement
# with MPG or you get the right to use the computer program from someone who is authorized to grant you that right.
# Any use of the computer program without a valid license is prohibited and liable to prosecution.
# Contact: ps-license@tuebingen.mpg.de
#
#
# If you use this code in a research publication please consider citing the following:
#
# STAR: Sparse Trained  Articulated Human Body Regressor <https://arxiv.org/pdf/2008.08535.pdf>
#
#
# Code Developed by:
# Ahmed A. A. Osman

import sys
sys.path.append('../')
sys.path.append('../../')
from STAR-Private.star.ch.star import STAR
import chumpy as ch
import numpy as np

from scipy.stats import truncnorm

import demo.cal_bone_length as bl

def get_truncated_normal(mean=0, sd=1, low=0, upp=10):
    return truncnorm(
        (low - mean) / sd, (upp - mean) / sd, loc=mean, scale=sd)

def save_as_obj(model,save_path, name):
    f_str = (model.f + 1).astype('str')
    f_anno = np.full((f_str.shape[0], 1), 'f')

    v_str = np.array(model).astype('str')
    v_anno = np.full((v_str.shape[0], 1), 'v')
    v = np.hstack((v_anno, v_str))
    f = np.hstack((f_anno, f_str))
    output = np.vstack((v, f))

    np.savetxt(save_path + name + ".obj", output, delimiter=" ", fmt="%s")


def extract_obj(save_path="./", name="output_2_0", betas=None):

    num_pose = 24 * 3
    num_betas = 300
    pose = ch.array(np.zeros(num_pose))

    if betas is None:
        betas = np.zeros(num_betas)
        betas[0] = 5.0
        betas[1] = 5.0
        # betas = np.array([2.94163568, 2.85407828, 2.52987061, -2.59662729, 1.83441506, 1.65966511
        #                           , 2.72223292, -1.83326521, 2.11696906, 0.72201226, -1.84460786, -2.28110441
        #                           , -1.07074934, -1.87749175, -0.05032597, -2.02162087, 1.4204214, 2.81279795
        #                           , -2.40832403, 1.53100512, -0.94323054, -2.78516985, -0.79193469, -2.09757654
        #                           , -1.62768206, -2.0686878, -2.32987997, -2.78497723, 2.20839839, -1.15458421
        #                           , 1.77175173, -1.87113229, 1.68661257, -2.03296359, 2.09280002, -1.56208689
        #                           , -2.38575696, -1.42501933, -1.00907489, 2.76840506, -0.9393906, -0.59641767
        #                           , 1.28480975, 2.29202402, 0.63988112, -2.65623052, -1.72974094, 1.72025593
        #                           , 2.56055951, -2.48436124, -2.57023051, 0.56334057, 1.76284953, 1.36488971
        #                           , 1.60566161, -1.61734355, -2.76394109, -2.03374668, 1.02847306, -2.15875549
        #                           , -1.00780287, 1.54319078, -0.45789869, -2.89439799, -1.49682128, -1.6018676
        #                           , 0.77742196, -1.3320165, 2.07106072, -0.29467458, 0.82903957, 2.58696502
        #                           , 0.52693933, 0.89843569, -0.04082294, 2.22580282, -1.10063747, 0.21182334
        #                           , 0.9693458, -0.00832858, -0.5248415, -0.20182403, 2.99733767, 0.20345353
        #                           , -2.52225332, 0.63742897, 2.8805035, 0.35439834, 2.64471466, -2.15352026
        #                           , -0.02450296, -2.21506661, -1.94992964, 1.20198535, -2.76361254, 2.66583318
        #                           , -2.70364913, 1.10319248, 2.60501457, -1.20715571, -1.50687088, -0.14487991
        #                           , 0.30471465, 1.1341939, -0.26091991, 2.18969929, -0.43011269, -2.77773015
        #                           , -0.77381005, 1.4367595, 2.79288353, 2.7550748, -1.36433918, -1.86696235
        #                           , 0.45539269, -0.58910841, -2.67544952, 0.72309428, 0.06291846, 2.19965453
        #                           , 2.62138064, -0.80651264, 2.71890527, 2.37475843, 1.74467831, 0.38381875
        #                           , -2.46479557, -2.87333564, -2.09020535, -0.03223871, 0.60391246, -1.01228899
        #                           , -2.4493562, 0.64352519, -1.29947768, -1.86431911, 0.87974452, 1.39009547
        #                           , 0.52867911, -1.70534762, 1.1950374, 2.15099562, -1.62751852, 2.12899475
        #                           , 0.9269436, -1.25606947, -2.4882879, -1.29922788, -2.61167278, 2.39144554
        #                           , -0.83802634, 2.84131322, 2.94253276, -0.47035511, -2.47803369, 2.60030411
        #                           , -1.44254344, -2.75725527, -2.10484361, -1.35952868, 1.00240204, 1.91912704
        #                           , -1.94978157, 2.81430341, 1.25014306, -2.82152717, 1.51805717, -0.62531289
        #                           , -1.12363444, 2.61272275, 0.06816942, 0.41557026, -0.55775195, -2.40785254
        #                           , -0.36730803, -1.75020186, -0.43392076, 1.69604492, 0.7757163, -0.33974641
        #                           , 0.57461064, -0.05223588, -1.04980214, 0.17479646, 1.54620639, -2.5023946
        #                           , -1.81104004, 1.81154191, 0.06335722, -1.10333712, 1.58450811, -2.08654831
        #                           , 1.68682292, -2.78354978, 2.82484993, 2.19792805, -0.05792083, -0.18225135
        #                           , -1.1243103, 0.96298362, 0.98307776, 1.87341605, 0.85224713, 2.8873046
        #                           , -1.65318007, -0.27706381, -0.89454656, 1.79315723, -1.42491709, 1.68342971
        #                           , 1.43509074, -1.07777616, 0.69476044, -2.02641789, 2.31017226, -2.60315485
        #                           , 1.3374964, -1.53231461, 1.5156364, -2.21061776, 2.76482735, -1.26884405
        #                           , 1.33900334, 1.89274523, 0.34139819, -2.8413538, -2.38196714, 2.30290458
        #                           , -2.04015952, 0.69332714, -0.66898055, 2.85291857, 0.49613841, 2.73096456
        #                           , 0.44951947, 2.36487015, -0.88468966, 0.91385147, 2.59899477, 2.67134361
        #                           , 0.53513449, 2.34350009, 2.16460145, -0.60664833, -2.26941403, -2.90936272
        #                           , -0.39688233, 2.17884259, -2.76673026, -1.18804681, -1.37969918, 1.77803259
        #                           , 1.65530126, 0.89276961, -1.04201571, 0.59897513, -2.20022921, -0.24548679
        #                           , -2.51063913, -1.07450199, -1.45027712, -2.70889226, -2.88834089, 0.39764583
        #                           , 1.28547342, 2.3040305, 2.26294672, -1.43824967, -1.97055483, 2.09088847
        #                           , 2.73254644, 0.2539685, -2.39962118, -1.19757399, -1.82799676, -1.35659195
        #                           , -2.02523996, -0.42688674, -2.06254038, -2.60064264, 1.57854412, -0.77841438
        #                           , 0.00710317, 2.5357915, -1.81310826, -0.04550116, -2.77099049, 0.03428283
        #                           , 2.72707113, -0.8630354, -0.5840501, -1.9047515, 0.15966643, -2.29604338
        #                           , 1.63157778, -0.06425265, 1.68518473, -2.460373, 2.91278618, 2.98347568])
    betas = ch.array(betas)

    model = STAR(gender='female',num_betas=num_betas, pose=pose,betas=betas)
    # ## Assign random pose and shape parameters
    # for j in range(0,10):
    #     model.betas[:] = 0.0  #Each loop all PC components are set to 0.
    #     for i in np.linspace(-3,3,10): #Varying the jth component +/- 3 standard deviations
    #         model.betas[j] = i
    #         model.betas = ch.array(np.zeros(num_betas)) #Betas
    # model.betas = ch.array(np.zeros(num_betas))  # Pose
    """
    model.betas = ch.array(np.array([ 2.94163568, 2.85407828, 2.52987061,-2.59662729, 1.83441506, 1.65966511
, 2.72223292,-1.83326521, 2.11696906, 0.72201226,-1.84460786,-2.28110441
,-1.07074934,-1.87749175,-0.05032597,-2.02162087, 1.4204214,  2.81279795
,-2.40832403, 1.53100512,-0.94323054,-2.78516985,-0.79193469,-2.09757654
,-1.62768206,-2.0686878,-2.32987997,-2.78497723, 2.20839839,-1.15458421
, 1.77175173,-1.87113229, 1.68661257,-2.03296359, 2.09280002,-1.56208689
,-2.38575696,-1.42501933,-1.00907489, 2.76840506,-0.9393906,-0.59641767
, 1.28480975, 2.29202402, 0.63988112,-2.65623052,-1.72974094, 1.72025593
, 2.56055951,-2.48436124,-2.57023051, 0.56334057, 1.76284953, 1.36488971
, 1.60566161,-1.61734355,-2.76394109,-2.03374668, 1.02847306,-2.15875549
,-1.00780287, 1.54319078,-0.45789869,-2.89439799,-1.49682128,-1.6018676
, 0.77742196,-1.3320165,  2.07106072,-0.29467458, 0.82903957, 2.58696502
, 0.52693933, 0.89843569,-0.04082294, 2.22580282,-1.10063747, 0.21182334
, 0.9693458,-0.00832858,-0.5248415,-0.20182403, 2.99733767, 0.20345353
,-2.52225332, 0.63742897, 2.8805035,  0.35439834, 2.64471466,-2.15352026
,-0.02450296,-2.21506661,-1.94992964, 1.20198535,-2.76361254, 2.66583318
,-2.70364913, 1.10319248, 2.60501457,-1.20715571,-1.50687088,-0.14487991
, 0.30471465, 1.1341939,-0.26091991, 2.18969929,-0.43011269,-2.77773015
,-0.77381005, 1.4367595,  2.79288353, 2.7550748,-1.36433918,-1.86696235
, 0.45539269,-0.58910841,-2.67544952, 0.72309428, 0.06291846, 2.19965453
, 2.62138064,-0.80651264, 2.71890527, 2.37475843, 1.74467831, 0.38381875
,-2.46479557,-2.87333564,-2.09020535,-0.03223871, 0.60391246,-1.01228899
,-2.4493562,  0.64352519,-1.29947768,-1.86431911, 0.87974452, 1.39009547
, 0.52867911,-1.70534762, 1.1950374,  2.15099562,-1.62751852, 2.12899475
, 0.9269436,-1.25606947,-2.4882879,-1.29922788,-2.61167278, 2.39144554
,-0.83802634, 2.84131322, 2.94253276,-0.47035511,-2.47803369, 2.60030411
,-1.44254344,-2.75725527,-2.10484361,-1.35952868, 1.00240204, 1.91912704
,-1.94978157, 2.81430341, 1.25014306,-2.82152717, 1.51805717,-0.62531289
,-1.12363444, 2.61272275, 0.06816942, 0.41557026,-0.55775195,-2.40785254
,-0.36730803,-1.75020186,-0.43392076, 1.69604492, 0.7757163,-0.33974641
, 0.57461064,-0.05223588,-1.04980214, 0.17479646, 1.54620639,-2.5023946
,-1.81104004, 1.81154191, 0.06335722,-1.10333712, 1.58450811,-2.08654831
, 1.68682292,-2.78354978, 2.82484993, 2.19792805,-0.05792083,-0.18225135
,-1.1243103,  0.96298362, 0.98307776, 1.87341605, 0.85224713, 2.8873046
,-1.65318007,-0.27706381,-0.89454656, 1.79315723,-1.42491709, 1.68342971
, 1.43509074,-1.07777616, 0.69476044,-2.02641789, 2.31017226,-2.60315485
, 1.3374964,-1.53231461, 1.5156364,-2.21061776, 2.76482735,-1.26884405
, 1.33900334, 1.89274523, 0.34139819,-2.8413538,-2.38196714, 2.30290458
,-2.04015952, 0.69332714,-0.66898055, 2.85291857, 0.49613841, 2.73096456
, 0.44951947, 2.36487015,-0.88468966, 0.91385147, 2.59899477, 2.67134361
, 0.53513449, 2.34350009, 2.16460145,-0.60664833,-2.26941403,-2.90936272
,-0.39688233, 2.17884259,-2.76673026,-1.18804681,-1.37969918, 1.77803259
, 1.65530126, 0.89276961,-1.04201571, 0.59897513,-2.20022921,-0.24548679
,-2.51063913,-1.07450199,-1.45027712,-2.70889226,-2.88834089, 0.39764583
, 1.28547342, 2.3040305,  2.26294672,-1.43824967,-1.97055483, 2.09088847
, 2.73254644, 0.2539685,-2.39962118,-1.19757399,-1.82799676,-1.35659195
,-2.02523996,-0.42688674,-2.06254038,-2.60064264, 1.57854412,-0.77841438
, 0.00710317, 2.5357915,-1.81310826,-0.04550116,-2.77099049, 0.03428283
, 2.72707113,-0.8630354,-0.5840501,-1.9047515,  0.15966643,-2.29604338
, 1.63157778,-0.06425265, 1.68518473,-2.460373,  2.91278618, 2.98347568]))  # Pose
    """
    # model.pose = ch.array(np.zeros(num_pose))  # Pose

    save_as_obj(model, save_path=save_path, name=name)


def make_data(base_data=np.zeros(0), save_path=None):
    num_pose = 24 * 3
    num_additional = 14

    if base_data.size == 0:
        num_betas = 300
        num_data = 30000
    else:
        num_data, num_betas = base_data.shape
    pose = ch.array(np.zeros(num_pose))  # Pose

    ret = np.zeros((num_data, num_betas + num_additional))



    for i in range(num_data):
        #if i%100 == 0:
        print (i)
        if base_data.size == 0:
            X = get_truncated_normal(mean=0, sd=3, low=-3, upp=3)
            betas_numpy = X.rvs(num_betas)
        else:
            betas_numpy = base_data[i,:num_betas]
        betas = ch.array(betas_numpy)
        model = STAR(gender='female', num_betas=num_betas, pose=pose, betas=betas)
        # [beta0 ... beta n v0_x v0_y v0_z v1_x v1_y v1_z ...]

        pos_vertices_vector = np.ravel(np.array(model.J_transformed))
        pos_J = bl.cal_bone(pos_vertices_vector)
        contents = np.hstack((betas_numpy, pos_J))
        ret[i,:] = contents[:]
        #print(contents[:])
#https://rfriend.tistory.com/358
    if save_path is not None:
        np.save(save_path, ret)
    return ret

def main():
    extract_obj()
    # ret_back = np.load('./saved_300betas_base.npy')
    # make_data(ret_back, './saved_210217.npy')
    # x_save_load = np.load('./saved.npy')
    # for i in range(0,10):
    #    print(x_save_load[i,:])


if __name__ == "__main__":
    main()