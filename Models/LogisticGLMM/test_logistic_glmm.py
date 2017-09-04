#!/usr/bin/python3
import VariationalBayes as vb
import LogisticGLMM_lib as logit_glmm
from VariationalBayes.SparseObjectives import \
    Objective, SparseObjective, pack_csr_matrix

import unittest
import numpy.testing as np_test
import numpy as np


def simulate_data(N, K, NG):
    np.random.seed(42)
    true_beta = np.array(range(K))
    true_beta = true_beta - np.mean(true_beta)
    true_mu = 0.
    true_tau = 40.0

    x_mat, y_g_vec, y_vec, true_rho, true_u = \
        logit_glmm.simulate_data(N, NG, true_beta, true_mu, true_tau)

    return x_mat, y_g_vec, y_vec

class TestModel(unittest.TestCase):

    # For every parameter type, execute all the required methods.
    def test_create_model(self):
        N = 50
        K = 2
        NG = 7

        x_mat, y_g_vec, y_vec = simulate_data(N, K, NG)
        prior_par = logit_glmm.get_default_prior_params(K)
        glmm_par = logit_glmm.get_glmm_parameters(K=K, NG=NG)

        model = logit_glmm.LogisticGLMM(
            glmm_par, prior_par, x_mat, y_vec, y_g_vec, num_gh_points=4)

        objective = Objective(model.glmm_par, model.get_kl)
        free_par = np.random.random(model.glmm_par.free_size())
        model.glmm_par.set_free(free_par)
        objective.fun_free(free_par)
        obj_grad = objective.fun_free_grad(free_par)
        obj_hess = objective.fun_free_hessian(free_par)
        obj_hvp = objective.fun_free_hvp(free_par, obj_grad)

        np_test.assert_array_almost_equal(
            np.matmul(obj_hess, obj_grad), obj_hvp)

        moment_wrapper = logit_glmm.MomentWrapper(glmm_par)
        moment_wrapper.get_moment_vector(free_par)

    def test_sparse_model(self):
        N = 17
        K = 2
        NG = 7

        x_mat, y_g_vec, y_vec = simulate_data(N, K, NG)
        prior_par = logit_glmm.get_default_prior_params(K)
        glmm_par = logit_glmm.get_glmm_parameters(K=K, NG=NG)

        model = logit_glmm.LogisticGLMM(
            glmm_par, prior_par, x_mat, y_vec, y_g_vec, num_gh_points=4)
        moment_wrapper = logit_glmm.MomentWrapper(glmm_par)
        objective = Objective(model.glmm_par, model.get_kl)

        free_par = np.random.random(model.glmm_par.free_size())

        sparse_model = logit_glmm.SparseModelObjective(
            glmm_par, prior_par, x_mat, y_vec, y_g_vec, num_gh_points=4,
            num_groups=1)

        sparse_model.glmm_par.set_free(free_par)

        ################################
        # Test get_data_for_groups

        g = 2
        group_rows, y_g_select = sparse_model.get_data_for_groups([g])
        np_test.assert_array_almost_equal(
            x_mat[group_rows, :], x_mat[y_g_vec == g, :])
        np_test.assert_array_almost_equal(
            y_vec[group_rows], y_vec[y_g_vec == g])
        self.assertEqual(len(y_g_select), sum(group_rows))

        ########################
        # Test the objectives.

        # Testing the local objective.
        print('Testing the groups\' elbo.')
        g = 2
        sparse_model.set_global_parameters()
        sparse_model.set_group_parameters([g])
        single_group_model = logit_glmm.LogisticGLMM(
            sparse_model.group_par, prior_par,
            x_mat[group_rows, :], y_vec[group_rows], y_g_select,
            num_gh_points=4)
        np_test.assert_array_almost_equal(
            single_group_model.glmm_par.get_vector(),
            sparse_model.group_par.get_vector(),
            err_msg='Group model parameter equality')

        single_group_elbo = single_group_model.get_elbo()
        sparse_elbo = sparse_model.get_global_elbo() + \
            sparse_model.get_group_elbo([g])

        np_test.assert_array_almost_equal(
            single_group_elbo, sparse_elbo, err_msg="Group model elbo equality")

        print('Testing full elbo.')
        sparse_elbo = sparse_model.get_global_elbo()
        for g in range(NG):
            sparse_model.set_group_parameters([g])
            sparse_elbo += sparse_model.get_group_elbo([g])

        elbo = -1 * objective.fun_free(free_par)
        np_test.assert_array_almost_equal(elbo, sparse_elbo)


if __name__ == '__main__':
    unittest.main()
