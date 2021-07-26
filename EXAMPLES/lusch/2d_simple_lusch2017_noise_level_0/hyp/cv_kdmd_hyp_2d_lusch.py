import numpy as np
import gc
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, '../../../../../')

from mpi4py import MPI
import pandas as pd
from SKDMD.MODEL_SRC.ckdmd import CKDMD
from sklearn.model_selection import KFold

def main(case, noise_level, rank_list):

    comm = MPI.COMM_WORLD
    size = comm.Get_size()
    rank = comm.Get_rank()

    # KDMD Options
    case_name = case + '_noise_level_' + str(noise_level)
    phase_space_range = [[-0.5, 0.5], [-0.5, 0.5]]
    ## original data
    total_numer_data = 1600
    kernel = 'gaussian'

    # prepare arg list
    if rank == 0:

        sigma_list = np.linspace(0.1, 10, 80)

        # prepare mpi job distribution
        mpi_job_total_list = []
        for sigma in sigma_list:
            for kdmd_rank in rank_list:
                mpi_job_total_list.append({'sigma':sigma, 'rank':kdmd_rank})

        # distribute jobs to each rank
        n_total = len(mpi_job_total_list)
        n_each = int(np.floor(n_total / size))

        mpi_job_each_rank_list = []
        for j in range(size - 1):
            mpi_job_each_rank_list.append(mpi_job_total_list[int(j * n_each) : int((j + 1) * n_each)])
        mpi_job_each_rank_list.append(mpi_job_total_list[int((size - 1) * n_each) : ])

    else:

        mpi_job_each_rank_list = None

    # each rank gets one job, the type of mpi_job_each_rank is still list
    mpi_job_each_rank = comm.scatter(mpi_job_each_rank_list, root=0)

    mpi_result_each_rank = []

    # for each rank, get its job done
    for arg_dict in mpi_job_each_rank:

        sigma = arg_dict.get('sigma')
        kdmd_rank = arg_dict.get('rank')

        config = {
            'model_case': case_name,
            'kernel': kernel,
            'sigma': sigma,
            'phase_space_range': phase_space_range,
            'reduced_rank': kdmd_rank,
            'cv_search_hyp':True
        }

        case_dir = './' + config['model_case']
        data = np.load(case_dir + '/' + str(total_numer_data) + '_trainData.npz')

        X = data['Xtrain']  # np.random.rand(50,2)
        Xdot = data['XdotTrain']  # np.random.rand(50, 2)

        print('')
        print('...KDMD....', ' sigma = ', config['sigma'], ' reduced_rank = ', config['reduced_rank'])
        print('')

        cv_inex = 0
        err_tr_list = []
        err_te_list = []
        num_tr_list = []
        # num_te_list = []

        # prepare data
        kf = KFold(n_splits=4, shuffle=True)

        # evaluate error in cross validation styl
        for train_index, test_index in kf.split(X):

            print('CV: ', cv_inex+1)
            print('')
            cv_inex += 1

            X_train, X_test = X[train_index], X[test_index]
            Xdot_train, Xdot_test = Xdot[train_index], Xdot[test_index]
            kdmdLearner = CKDMD(config)
            err_tr, err_te, num_tr = kdmdLearner.train_with_valid(X=X_train,
                                                                  Xdot=Xdot_train,
                                                                  X_val=X_test,
                                                                  Xdot_val=Xdot_test,
                                                                  criterion_threshold=0.05)

            criterion_threshold = kdmdLearner.criterion_threshold

            err_te_list.append(err_te)
            err_tr_list.append(err_tr)
            num_tr_list.append(num_tr)
            # num_te_list.append(num_te)

            gc.collect()
            print('')

        ave_num_tr = np.mean(np.array(num_tr_list))
        ave_err_tr = np.mean(np.array(err_tr_list))
        ave_err_te = np.mean(np.array(err_te_list))

        print('================================================')
        print('for sigma = ', sigma, ' rank = ', kdmd_rank)
        print('average train error = ', ave_err_tr)
        print('average test error = ', ave_err_te)
        print('average num good eigfunction with relative error below ' + str(criterion_threshold*100) + '% for both train and test = ', ave_num_tr)
        print('================================================')

        # append results together with args
        mpi_result_each_rank.append({'sigma': sigma,
                                     'rank':kdmd_rank,
                                     'ave. train error': ave_err_tr,
                                     'ave. test error': ave_err_te,
                                     'ave. num for both train and test':ave_num_tr})

    # combine into tables
    df = pd.DataFrame(mpi_result_each_rank)

    # concatate across ranks
    final_df_list = comm.gather(df, root=0)

    if rank == 0:

        print("")
        print("")

        # concate a list of pandas datafram
        final_df = pd.concat(final_df_list)

        # save to csv
        final_df.to_csv(r'./hyp.csv', index=None, header=True)  # Don't forget to add '.csv' at the end of the path

        print("")
        print("")
        print("========================================================")
        print('summary of computational results = ', final_df)



if __name__ == '__main__':

    case = '2d_simple_lusch2017'
    noise_level = 0

    rank_list = [34, 50, 70]

    main(case,noise_level, rank_list)


