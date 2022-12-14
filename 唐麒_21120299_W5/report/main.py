# -*- coding: utf-8 -*-
import cv2
import os
import numpy as np
import pickle
import matplotlib.pyplot as plt
import time

# 值越大，前景被当作背景的可能性也越大
# 值越小，背景被当作前景的可能性也越大
SIGMA = 30  # 可调整的参数
WEIGHT = 0.1  # 可调整的参数


# 图像GMM模型定义
class GmmModel:
    def __init__(self, sample_image):
        # 像素点个数
        self.img_size = sample_image.shape[0] * sample_image.shape[1]
        # 各像素点的模型个数 （初始化为0）
        self.model_count = np.zeros([1, self.img_size], int)
        # GMM高斯模型的个数 K （这里是固定的，有些方法可以对每个像素进行自适应模型个数K的选取）
        self.k = 4  # 可调整的参数
        # 学习率 Alpha
        self.alpha = 0.005  # 可调整的参数
        # SumOfWeightThreshold T
        self.t = 0.75  # 可调整的参数
        # 各个模型的权重系数（初始化为0）
        self.w = np.zeros([self.k, self.img_size])
        # 各高斯模型的均值（初始化为0）
        self.u = np.zeros([self.k, self.img_size])
        # 各高斯模型的标准差（初始化为默认值）
        self.sigma = np.full([self.k, self.img_size], SIGMA)


# 读取图片集合，返回灰度图
def load_data_set(path):
    image_set = []
    file_names = os.listdir(path)
    if "0000.jpg" in file_names:
        start = 1
        end = 109
    else:
        start = 109
        end = 201

    for pic_i in range(start, end):
        if pic_i < 10:
            pic_name = "000%d.jpg" % pic_i
        elif 100 > pic_i >= 10:
            pic_name = "00%d.jpg" % pic_i
        else:
            pic_name = "0%d.jpg" % pic_i
        file_path = os.path.join(path, pic_name)
        # 以灰度图的形式读取
        img = cv2.imread(file_path, cv2.IMREAD_GRAYSCALE)
        image_set.append(img)
    return image_set


# gmm模型初始化
def gmm_model_create():
    # 读取首张图片帧
    first_frame = cv2.imread('./Scene_Data/0000.jpg', cv2.IMREAD_GRAYSCALE)
    return GmmModel(first_frame)


# 训练模型参数
def gmm_model_train(gmm_model, single_frame):
    # start_time = time.time()
    img_rows = single_frame.shape[0]
    img_cols = single_frame.shape[1]
    for m in range(img_rows):
        for n in range(img_cols):
            # 用于标识是否存在与像素点(m,n)匹配的分布模型
            matched = False
            for k in range(gmm_model.model_count[0, m * img_cols + n]):
                # 计算像素点与高斯分布均值的差值
                difference = abs(single_frame[m, n] - gmm_model.u[k, m * img_cols + n])
                distance = difference * difference
                # 当前像素点满足当前高斯分布
                if difference <= 2.5 * gmm_model.sigma[k, m * img_cols + n]:
                    matched = True
                    # 更新第k个高斯分布模型的参数
                    # 计算第k个高斯分布在该像素点上的概率密度
                    prob = (1 / (2 * np.pi * gmm_model.sigma[k, m * img_cols + n] ** 2) ** 0.5) * np.exp(
                        -(single_frame[m, n] - gmm_model.u[k, m * img_cols + n]) ** 2 / (
                                2 * (gmm_model.sigma[k, m * img_cols + n] ** 2)))
                    p = gmm_model.alpha * prob
                    # update weight
                    gmm_model.w[k, m * img_cols + n] = (1 - gmm_model.alpha) * gmm_model.w[
                        k, m * img_cols + n] + gmm_model.alpha
                    # update mean
                    gmm_model.u[k, m * img_cols + n] = (1 - p) * gmm_model.u[k, m * img_cols + n] + p * single_frame[
                        m, n]
                    # update standard deviation
                    if gmm_model.sigma[k, m * img_cols + n] < SIGMA / 2:
                        gmm_model.sigma[k, m * img_cols + n] = SIGMA / 2
                    else:
                        gmm_model.sigma[k, m * img_cols + n] = ((1 - p) * gmm_model.sigma[
                            k, m * img_cols + n] ** 2 + p * distance) ** 0.5
                    break
                else:
                    # 当前像素点不满足当前高斯分布
                    # 只更新weight
                    gmm_model.w[k, m * img_cols + n] = (1 - gmm_model.alpha) * gmm_model.w[k, m * img_cols + n]
                # 对k个gmm_model进行排序，便于后面高斯分布模型的替换和更新
                gmm_model_sort(gmm_model, m, n, img_cols)
            '''
            # 当前像素点未匹配到任何一个高斯分布，则需要新建一个高斯分布
            # 这里需要考虑两种情况
            # 1. 存在未初始化的高斯分布：此时可新建一个高斯分布
            # 2. k个高斯分布均已被初始化：此时替换order_weight最低的分布模型
            '''
            if not matched:
                # print('(', m, ',', n, ')', 'no matching distribution')
                # condition 1
                model_count = gmm_model.model_count[0, m * img_cols + n]
                if model_count < gmm_model.k:
                    # 初始化weight
                    gmm_model.w[model_count, m * img_cols + n] = WEIGHT
                    # 初始化mean
                    gmm_model.u[model_count, m * img_cols + n] = single_frame[m, n]
                    # 初始化standard deviation
                    gmm_model.sigma[model_count, m * img_cols + n] = SIGMA
                    gmm_model.model_count[0, m * img_cols + n] = model_count + 1
                # condition 2
                else:
                    # update weight
                    gmm_model.w[gmm_model.k - 1, m * img_cols + n] = WEIGHT
                    # update mean
                    gmm_model.u[gmm_model.k - 1, m * img_cols + n] = single_frame[m, n]
                    # update standard deviation
                    gmm_model.sigma[gmm_model.k - 1, m * img_cols + n] = SIGMA
            # weight归一化
            # 加上此判断条件，运行速度快了很多
            if sum(gmm_model.w[:, m * img_cols + n]) != 0:
                gmm_model.w[:, m * img_cols + n] = gmm_model.w[:, m * img_cols + n] / sum(
                    gmm_model.w[:, m * img_cols + n])
    # end_time = time.time()
    # print(end_time - start_time)


# 对指定像素点的k个gmm_model进行排序(依据：w/sigma)
def gmm_model_sort(gmm_model, m, n, img_cols):
    # 构造排序依据
    order_weight = gmm_model.w[:, m * img_cols + n] / gmm_model.sigma[:, m * img_cols + n]
    # 封装order_weight和权重
    zip_ow_weight = zip(order_weight, gmm_model.w[:, m * img_cols + n])
    # 封装order_weight和均值
    zip_ow_mean = zip(order_weight, gmm_model.u[:, m * img_cols + n])
    # 封装order_weight和标准差
    zip_ow_standard_deviation = zip(order_weight, gmm_model.sigma[:, m * img_cols + n])
    zip_ow_weight = sorted(zip_ow_weight, reverse=True)
    zip_ow_mean = sorted(zip_ow_mean, reverse=True)
    zip_ow_standard_deviation = sorted(zip_ow_standard_deviation, reverse=True)
    temp, gmm_model.w[:, m * img_cols + n] = zip(*zip_ow_weight)
    temp, gmm_model.u[:, m * img_cols + n] = zip(*zip_ow_mean)
    temp, gmm_model.sigma[:, m * img_cols + n] = zip(*zip_ow_standard_deviation)


# 借助形态学处理操作消除噪声点、连通对象
def optimize_frame(single_frame):
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    # kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    frame_parsed = cv2.morphologyEx(single_frame, cv2.MORPH_OPEN, kernel, iterations=1)
    frame_parsed = cv2.morphologyEx(frame_parsed, cv2.MORPH_CLOSE, kernel, iterations=3)
    return frame_parsed


# 根据训练得到的GMM模型，对输入图像进行背景剪除操作，将处理后的图像返回
def background_subtract(gmm_model, single_frame):
    # 首先对计算得到的高斯模型进行筛选 需要满足条件sum(weight_i)>T
    img_rows = single_frame.shape[0]
    img_cols = single_frame.shape[1]
    for pixel_index in range(img_rows * img_cols):
        weight_sum = 0
        for k in range(gmm_model.model_count[0, pixel_index]):
            weight_sum = weight_sum + gmm_model.w[k, pixel_index]
            # 如果前K个模型已经满足权重阈值，则只选择前K个模型
            if weight_sum > gmm_model.t:
                gmm_model.model_count[0, pixel_index] = k + 1
                break
    # 初始化处理后的图片
    frame_parsed = np.full([img_rows, img_cols], 255, np.uint8)
    for m in range(img_rows):
        for n in range(img_cols):
            hit = False
            for k in range(gmm_model.model_count[0, m * img_cols + n]):
                # 计算当前像素与高斯分布均值的差值
                difference = abs(single_frame[m, n] - gmm_model.u[k, m * img_cols + n])
                if difference <= 2 * gmm_model.sigma[k, m * img_cols + n]:
                    # 背景
                    hit = True
                    break
            if hit:
                # 前景
                frame_parsed[m, n] = 0
    return frame_parsed


# 保存GMM模型到本地
def gmm_model_save(gmm_model, path):
    with open(path, 'wb') as f:
        pickle.dump(gmm_model, f)


# 加载本地GMM模型
def gmm_model_load(path):
    with open(path, 'rb') as f:
        gmm_model = pickle.load(f)
    return gmm_model


if __name__ == '__main__':
    # 初始化GMM模型
    model = gmm_model_create()
    gmm_model_path = './models_learned/gmm_model_maxK={0}_alpha={1}_T={2}_sigma={3}.pkl'.format(model.k, model.alpha,
                                                                                                model.t, SIGMA)
    # 如果模型已存在则直接加载
    if not os.path.exists(gmm_model_path):
        # 加载训练集
        frames = load_data_set('./Scene_Data_Copy/Background_Train/')
        for i in range(len(frames)):
            print('frame ' + str(i) + ' is training...')
            gmm_model_train(model, frames[i])
        print('GMM Model learning process finished')
        print('saving model...')
        gmm_model_save(model, gmm_model_path)
    else:
        print('local model already exists')
    print('loading model...\n', gmm_model_path)
    # 加载本地模型
    model = gmm_model_load(gmm_model_path)
    frames = load_data_set('./Scene_Data_Copy/Car_In/')
    # 实时显示剪除效果
    param_str = 'maxK={0} alpha={1} T={2} SIGMA={3}'.format(model.k, model.alpha, model.t, SIGMA)
    # plt.ion()

    total_time = 0
    num_frame = 0
    for i in range(len(frames)):
        num_frame += 1
        start_time = time.time()
        # 背景剪除后
        frame_subtracted = background_subtract(model, frames[i])
        # 形态学处理优化
        frame_optimized = optimize_frame(frame_subtracted)

        cv2.imshow("Scene", frame_optimized)
        k = cv2.waitKey(60) & 0xff
        cost = time.time() - start_time
        total_time += cost
        if k == 27:
            break
    print("单张耗时:", total_time / num_frame, "每秒处理:", 1 / total_time)

    #     plt.suptitle('(Frame {0}) RealTime Background Subtract\n\n{1}'.format(i + 1, param_str))
    #     plt.subplot(131)
    #     plt.title('origin')
    #     plt.imshow(frames[i], cmap='gray')
    #     plt.subplot(132)
    #     plt.title('subtracted')
    #     plt.imshow(frame_subtracted, cmap='gray')
    #     plt.subplot(133)
    #     plt.title('optimized')
    #     plt.imshow(frame_optimized, cmap='gray')
    #     plt.pause(0.2)
    #     plt.clf()
    # plt.ioff()
