#!/usr/bin/env python3

import autograd
from autograd import numpy as np
import scipy as sp
import numpy.testing as np_test
import unittest
import LinearResponseVariationalBayes as vb
import LinearResponseVariationalBayes.SparseObjectives as obj_lib
import LinearResponseVariationalBayes.ConjugateGradient as cg


class Model(object):
    def __init__(self, dim):
        self.dim = dim
        self.x = vb.VectorParam('x', size=dim, lb=-2.0, ub=5.0)
        self.y = vb.VectorParam('y', size=dim, lb=-2.0, ub=5.0)
        self.a_mat = np.full((dim, dim), 0.1) + np.eye(dim)
        self.set_inits()

        self.opt_x = np.linspace(1., 2., self.dim)

        self.preconditioner = np.eye(dim)

    def set_random(self):
        self.x.set_free(np.random.random(self.x.free_size()))

    def set_inits(self):
        #self.x.set_vector(np.ones(self.dim))
        self.x.set_vector(np.linspace(0., 1., self.dim))

    def set_opt(self):
        self.x.set_vector(self.opt_x)

    def f_of_x(self, x):
        x_c = x - self.opt_x
        return np.matmul(x_c.T, np.matmul(self.a_mat, x_c))

    def f(self):
        return self.f_of_x(self.x.get())

    def f_conditioned(self):
        # Note that
        # df / dy = (dx' / dy) df / dx = (dy / dx')^{-1} df / dx
        # So the transform should multiply by the inverse of the preconditioner.
        y_free = np.matmul(self.preconditioner, self.x.get_free())
        self.y.set_free(y_free)
        return self.f_of_x(self.y.get())


class TwoParamModel(object):
    def __init__(self, dim=3):
        self.a = np.random.random((dim, dim))
        self.a = np.matmul(self.a, np.transpose(self.a)) + np.eye(dim)

        self.par = vb.ModelParamsDict()
        self.par.push_param(vb.VectorParam('x', size=dim, lb=0))
        self.par.push_param(vb.VectorParam('y', size=dim))

    def set_random(self):
        self.par.set_free(np.random.random(self.par.free_size()))

    def fun(self):
        x = self.par['x'].get()
        y = self.par['y'].get()
        return np.matmul(np.matmul(np.transpose(x), self.a), y)



class TestObjectiveClass(unittest.TestCase):
    # For every parameter type, execute all the required methods.
    def test_objective(self):
        model = Model(dim=3)
        objective = obj_lib.Objective(par=model.x, fun=model.f)

        model.set_inits()
        x_free = model.x.get_free()
        x_vec = model.x.get_vector()

        model.set_opt()
        self.assertTrue(objective.fun_free(x_free) > 0.0)
        np_test.assert_array_almost_equal(
            objective.fun_free(x_free), objective.fun_vector(x_vec))

        grad = objective.fun_free_grad(x_free)
        hess = objective.fun_free_hessian(x_free)
        np_test.assert_array_almost_equal(
            np.matmul(hess, grad), objective.fun_free_hvp(x_free, grad))

        #model.set_opt()
        self.assertTrue(objective.fun_vector(x_vec) > 0.0)
        grad = objective.fun_vector_grad(x_vec)
        hess = objective.fun_vector_hessian(x_vec)
        np_test.assert_array_almost_equal(
            np.matmul(hess, grad), objective.fun_vector_hvp(x_free, grad))

        # Test the preconditioning
        preconditioner = 2.0 * np.eye(model.dim)
        preconditioner[model.dim - 1, 0] = 0.1 # Add asymmetry for testing!
        objective.preconditioner = preconditioner

        np_test.assert_array_almost_equal(
            objective.fun_free_cond(x_free),
            objective.fun_free(np.matmul(preconditioner, x_free)),
            err_msg='Conditioned function values')

        fun_free_cond_grad = autograd.grad(objective.fun_free_cond)
        grad_cond = objective.fun_free_grad_cond(x_free)
        np_test.assert_array_almost_equal(
            fun_free_cond_grad(x_free), grad_cond,
            err_msg='Conditioned gradient values')

        fun_free_cond_hessian = autograd.hessian(objective.fun_free_cond)
        hess_cond = objective.fun_free_hessian_cond(x_free)
        np_test.assert_array_almost_equal(
            fun_free_cond_hessian(x_free), hess_cond,
            err_msg='Conditioned Hessian values')

        fun_free_cond_hvp = autograd.hessian_vector_product(
            objective.fun_free_cond)
        np_test.assert_array_almost_equal(
            fun_free_cond_hvp(x_free, grad_cond),
            objective.fun_free_hvp_cond(x_free, grad_cond),
            err_msg='Conditioned Hessian vector product values')


    def test_two_parameter_objective(self):
        model = TwoParamModel()
        model.set_random()

        objective_full = obj_lib.Objective(model.par, model.fun)

        objective_x = obj_lib.Objective(model.par['x'], model.fun)
        objective_y = obj_lib.Objective(model.par['y'], model.fun)

        objective = obj_lib.TwoParameterObjective(
            model.par['x'], model.par['y'], model.fun)

        par_free = model.par.get_free()
        par_vec = model.par.get_vector()
        x_free = model.par['x'].get_free()
        y_free = model.par['y'].get_free()
        x_vec = model.par['x'].get_vector()
        y_vec = model.par['y'].get_vector()

        np_test.assert_array_almost_equal(
            model.fun(), objective.fun_free(x_free, y_free))
        np_test.assert_array_almost_equal(
            model.fun(), objective.fun_free(x_free, y_free))
        np_test.assert_array_almost_equal(
            model.fun(), objective.fun_vector(x_vec, y_vec))

        np_test.assert_array_almost_equal(
            objective.ag_fun_free_grad1(x_free, y_free),
            objective_x.ag_fun_free_grad(x_free))

        np_test.assert_array_almost_equal(
            objective.ag_fun_free_grad2(x_free, y_free),
            objective_y.ag_fun_free_grad(y_free))

        np_test.assert_array_almost_equal(
            objective.ag_fun_vector_grad1(x_vec, y_vec),
            objective_x.ag_fun_vector_grad(x_vec))

        np_test.assert_array_almost_equal(
            objective.ag_fun_vector_grad2(x_vec, y_vec),
            objective_y.ag_fun_vector_grad(y_vec))


    def run_optimization_tests(self, use_sparse=False):
        model = Model(dim=3)
        objective = obj_lib.Objective(par=model.x, fun=model.f)
        preconditioner = 2.0 * np.eye(model.dim)
        preconditioner[model.dim - 1, 0] = 0.1 # Add asymmetry for testing!

        if use_sparse:
            objective.preconditioner = preconditioner
        else:
            objective.preconditioner = sp.sparse.csr_matrix(preconditioner)

        model.set_inits()
        x0 = model.x.get_free()
        y0 = np.linalg.solve(preconditioner, x0)

        # Unconditioned
        opt_result = sp.optimize.minimize(
            fun=objective.fun_free,
            jac=objective.fun_free_grad,
            hessp=objective.fun_free_hvp,
            x0=x0,
            method='trust-ncg',
            options={'maxiter': 100, 'disp': False, 'gtol': 1e-6 })
        self.assertTrue(opt_result.success)
        model.x.set_free(opt_result.x)
        np_test.assert_array_almost_equal(
            model.opt_x, model.x.get_vector(),
            err_msg='Trust-NCG Unconditioned')

        # Conditioned:
        opt_result = sp.optimize.minimize(
            fun=objective.fun_free_cond,
            jac=objective.fun_free_grad_cond,
            hessp=objective.fun_free_hvp_cond,
            x0=y0,
            method='trust-ncg',
            options={'maxiter': 100, 'disp': False, 'gtol': 1e-6 })
        self.assertTrue(opt_result.success)
        model.x.set_free(objective.uncondition_x(opt_result.x))
        np_test.assert_array_almost_equal(
            model.opt_x, model.x.get_vector(),
            err_msg='Trust-NCG')

        opt_result = sp.optimize.minimize(
            fun=lambda par: objective.fun_free_cond(par, verbose=False),
            jac=objective.fun_free_grad_cond,
            x0=y0,
            method='BFGS',
            options={'maxiter': 100, 'disp': False, 'gtol': 1e-6 })
        self.assertTrue(opt_result.success)
        model.x.set_free(objective.uncondition_x(opt_result.x))
        np_test.assert_array_almost_equal(
            model.opt_x, model.x.get_vector(), err_msg='BFGS')

        opt_result = sp.optimize.minimize(
            fun=lambda par: objective.fun_free_cond(par, verbose=False),
            jac=objective.fun_free_grad_cond,
            hess=objective.fun_free_hessian_cond,
            x0=y0,
            method='Newton-CG',
            options={'maxiter': 100, 'disp': False })
        self.assertTrue(opt_result.success)
        model.x.set_free(objective.uncondition_x(opt_result.x))
        np_test.assert_array_almost_equal(
            model.opt_x, model.x.get_vector(), err_msg='Newton')

    def test_optimization(self):
        self.run_optimization_tests(use_sparse=True)
        self.run_optimization_tests(use_sparse=False)


class TestSparsePacking(unittest.TestCase):
    def test_safe_matmul(self):
        def safe_matmul_todense(a, b):
            result = obj_lib.safe_matmul(a, b)
            if sp.sparse.issparse(result):
                return np.asarray(result.todense())
            else:
                return np.asarray(result)

        a = np.random.random((3, 3))
        b = np.random.random((3, 3))
        ab = np.matmul(a, b)

        np_test.assert_array_almost_equal(
            ab, safe_matmul_todense(a, b))
        np_test.assert_array_almost_equal(
            ab, safe_matmul_todense(sp.sparse.csr_matrix(a), b))
        np_test.assert_array_almost_equal(
            ab, safe_matmul_todense(a, sp.sparse.csr_matrix(b)))
        np_test.assert_array_almost_equal(
            ab, safe_matmul_todense(np.matrix(a), b))
        np_test.assert_array_almost_equal(
            ab, safe_matmul_todense(a, np.matrix(b)))

    def test_packing(self):
        dense_mat = np.zeros((3, 3))
        dense_mat[0, 0] = 2.0
        dense_mat[0, 1] = 3.0
        dense_mat[2, 1] = 4.0

        sparse_mat = sp.sparse.csr_matrix(dense_mat)
        sparse_mat_packed = obj_lib.pack_csr_matrix(sparse_mat)
        sparse_mat_unpacked = obj_lib.unpack_csr_matrix(sparse_mat_packed)

        np_test.assert_array_almost_equal(
            dense_mat, sparse_mat_unpacked.todense())


class TestIndexParams(unittest.TestCase):
    def test_index_params(self):
        dim = 3
        param = vb.ModelParamsDict('test')
        param.push_param(vb.VectorParam('x', size=dim, lb=-2.0, ub=5.0))
        param.push_param(vb.VectorParam('y', size=dim, lb=-2.0, ub=5.0))

        index_par = obj_lib.make_index_param(param)
        param.set_free(np.random.random(param.free_size()))
        param_vec = param.get_vector()

        for d in range(dim):
            for pname in ['x', 'y']:
                self.assertAlmostEqual(
                    param[pname].get()[d],
                    param_vec[index_par[pname].get()[d]])


class TestConjugateGradient(unittest.TestCase):
    def test_masking(self):
        masks = cg.get_masks(20, 3)
        self.assertTrue(np.max([ np.sum(m) for m in masks]) <= 3)
        all_m = np.full(20, False)
        no_m = np.full(20, True)
        for m in masks:
            all_m = np.logical_or(all_m, m)
            no_m = np.logical_xor(no_m, m)
        self.assertTrue(np.all(all_m))
        self.assertTrue(~np.any(no_m))

    def test_cg(self):
        K = 50
        mat = np.random.random((K, K))
        mat = 0.5 * (mat + mat.transpose()) + 10 * np.eye(K)
        loc = np.array([float(k) / 7. for k in range(K)])
        def ObjPar(par, mat, loc):
            diff = par - loc
            return np.dot(diff, np.matmul(mat, diff))

        x = loc + 0.1 * np.random.rand(K)

        ObjPar(x, mat, loc)
        Obj = lambda x: ObjPar(x, mat, loc)
        ObjHess = autograd.hessian(Obj)
        ObjHessVecProd = autograd.hessian_vector_product(Obj)

        masks = cg.get_masks(K, 10)
        cg_solver = cg.ConjugateGradientSolver(ObjHessVecProd, loc)
        cg_solver.get_hinv_vec_subsets(x, masks, verbose=False)

        hess = ObjHess(loc)
        cho_factor = sp.linalg.cho_factor(hess)

        chol_hinv_vecs = []
        for vec in cg_solver.vecs:
            hinv_vec = sp.linalg.cho_solve(cho_factor, vec)
            chol_hinv_vecs.append(hinv_vec)

        diffs = [ np.max(np.abs(cg_solver.hinv_vecs[ind] -
                         chol_hinv_vecs[ind])) for ind in range(len(masks))]
        self.assertTrue(np.max(diffs) < 1e-8)


if __name__ == '__main__':
    unittest.main()
