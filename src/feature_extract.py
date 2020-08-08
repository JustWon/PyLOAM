import numpy as np

class FeatureExtract:
    def __init__(self, config=None):
        self.config = config
        self.LINE_NUM = 16
        self.RING_INDEX = 4
        self.THRES = 2
    
    def remove_close_points(self, cloud, thres):
        """ Input size: N*3 """
        dists = np.sum(np.square(cloud[:, :3]), axis=1)
        cloud_out = cloud[dists > thres*thres]
        return cloud_out

    def divide_lines(self, cloud):
        clouds_by_line = [cloud[cloud[:, self.RING_INDEX] == val, :] for val in range(0, self.LINE_NUM)]
        cloud_out = np.concatenate(clouds_by_line, axis=0)
        return cloud_out

    def compute_curvatures(self, cloud):
        kernel = np.ones(11)
        kernel[5] = -10
        curvatures = np.apply_along_axis(lambda x: np.convolve(x, kernel, 'same'), 0, cloud[:, :3])
        curvatures = np.sum(np.square(curvatures), axis=1)
        scan_start_id = [np.where(cloud[:, self.RING_INDEX] == val)[0][0] + 5 for val in range(0, self.LINE_NUM)]
        scan_end_id = [np.where(cloud[:, self.RING_INDEX] == val)[0][-1] - 5 for val in range(0, self.LINE_NUM)]
        return curvatures, scan_start_id, scan_end_id

    def remove_occluded(self, cloud):
        num_points = cloud.shape[0]
        depth = np.sqrt(np.sum(np.square(cloud[:, :3]), axis=1))
        picked_list = np.zeros(num_points, dtype=int)
        for i in range(5, num_points-6):
            diff = np.sum(np.square(cloud[i, :3] - cloud[i+1, :3]))
            if diff > 0.1:
                if depth[i] > depth[i+1]:
                    depth_diff = cloud[i+1, :3] - cloud[i, :3] * (depth[i+1]/depth[i])
                    depth_diff = np.sqrt(np.sum(np.square(depth_diff)))
                    if depth_diff/depth[i+1] < 0.1:
                        picked_list[i-5:i+1] = 1
                else:
                    depth_diff = cloud[i+1, :3] * (depth[i]/depth[i+1]) - cloud[i, :3]
                    depth_diff = np.sqrt(np.sum(np.square(depth_diff)))
                    if depth_diff/depth[i] < 0.1:
                        picked_list[i+1:i+6] = 1

            diff_prev = np.sum(np.square(cloud[i, :3] - cloud[i-1, :3]))
            if diff > 0.0002 * depth[i] and diff_prev > 0.0002 * depth[i]:
                picked_list[i] = 1

        return picked_list

    def feature_classification(self, cloud, curvatures, picked_list, scan_start_id, scan_end_id):
        corner_sharp = []
        corner_less = []
        surf_flat = []
        surf_less = []
        cloud_labels = np.zeros(cloud.shape[0])
        index = np.arange(cloud.shape[0])
        index = np.expand_dims(index, axis=1).astype('float64')
        curvatures = np.expand_dims(curvatures, axis=1)

        curv_index = np.hstack((curvatures, index))
        for scan_id in range(self.LINE_NUM):
            for i in range(6):
                sp = int((scan_start_id[scan_id] * (6-i) + scan_end_id[scan_id] * i) / 6)
                ep = int((scan_start_id[scan_id] * (5-i) + scan_end_id[scan_id] * (i+1)) / 6 + 1)

                curv_seg = curv_index[sp:ep, :]
                sorted_curv = curv_seg[np.argsort(curv_seg[:, 0])]
                picked_num = 0

                for j in range(ep-1, sp+1, -1):
                    sorted_ind = j - sp
                    ind = int(sorted_curv[sorted_ind, 1])
                    curv = sorted_curv[sorted_ind, 0]
                    if picked_list[ind] == 0 and curv > 0.1:
                        picked_num += 1
                        if picked_num <= 2:
                            cloud_labels[ind] = 2
                            corner_sharp.append(ind)
                            corner_less.append(ind)
                        elif picked_num <= 20:
                            cloud_labels[ind] = 1
                            corner_less.append(ind)
                        else:
                            break

                        picked_list[ind] = 1

                        for l in range(1,6):
                            diff = np.sum(np.square(cloud[ind+l, :3] - cloud[ind+l-1, :3]))
                            if diff > 0.05:
                                break
                            picked_list[ind+l] = 1

                        for l in range(-1, -6, -1):
                            diff = np.sum(np.square(cloud[ind+l, :3] - cloud[ind+l+1, :3]))
                            if diff > 0.05:
                                break
                            picked_list[ind+l] = 1
                
                picked_num = 0
                for j in range(sp, ep):
                    sorted_ind = j - sp
                    ind = int(sorted_curv[sorted_ind, 1])
                    curv = sorted_curv[sorted_ind, 0]
                    if picked_list[ind] == 0 and curv < 0.1:
                        cloud_labels[ind] = -1
                        surf_flat.append(ind)
                        picked_num += 1

                        if picked_num >= 4:
                            break
                        
                        picked_list[ind] = 1

                        for l in range(1,6):
                            diff = np.sum(np.square(cloud[ind+l, :3] - cloud[ind+l-1, :3]))
                            if diff > 0.05:
                                break
                            picked_list[ind+l] = 1

                        for l in range(-1, -6, -1):
                            diff = np.sum(np.square(cloud[ind+l, :3] - cloud[ind+l+1, :3]))
                            if diff > 0.05:
                                break
                            picked_list[ind+l] = 1
                
                for j in range(sp, ep):
                    sorted_ind = j - sp
                    ind = int(sorted_curv[sorted_ind, 1])
                    if cloud_labels[ind] <= 0:
                        surf_less.append(ind)
        
        return corner_sharp, corner_less, surf_flat, surf_less

    def feature_extract(self, cloud):
        cloud = self.remove_close_points(cloud, self.THRES)
        cloud = self.divide_lines(cloud)
        curvatures, scan_start_id, scan_end_id = self.compute_curvatures(cloud)
        picked_list = self.remove_occluded(cloud)
        corner_sharp, corner_less, surf_flat, surf_less = self.feature_classification(cloud, curvatures, picked_list, scan_start_id, scan_end_id)
        return cloud[corner_sharp, :], cloud[corner_less, :], cloud[surf_flat, :], cloud[surf_less, :]
