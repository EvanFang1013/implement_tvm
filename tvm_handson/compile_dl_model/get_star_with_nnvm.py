# nnvm workflow
import nnvm.compiler
import nnvm.symbol as sym

x = sym.Variable('x')
y = sym.Variable('y')
z = sym.elemwise_add(x, sym.sqrt(y))
compute_graph = nnvm.graph.create(z)
print("--------compute graph---------")
print(compute_graph.ir())

shape = (4,)
# 输入是一个z:nnvm.symbol,输出deply_graph:nnvm.symbol,这是经过nnvm优化之后的图
# 也就是说图优化这个步骤实在nnvm里面进行的
deploy_graph, lib, _ = nnvm.compiler.build(z, target='cuda',
                                           shape={'x': shape}, dtype='float32')

print('---------deploy graph----------')
print(deploy_graph.ir())

# lib:host module lib.imported_modules[0]:a device module
# 现在的疑问是:这个fuse opt是 nnvm 中手写的优化算子,还是自动生成的优化算子?
print('---------deploy lib------------')
print(lib.imported_modules[0].get_source())

# deploy and run
import tvm
import numpy as np
from tvm.contrib import graph_runtime

module = graph_runtime.create(deploy_graph, lib, ctx=tvm.gpu())

x_np = np.array([1, 2, 3, 4]).astype("float32")
y_np = np.array([4, 4, 4, 4]).astype("float32")
# set input to the graph module
module.set_input(x=x_np, y=y_np)
module.run()
out = module.get_output(0, tvm.nd.empty(shape))
print(out.asnumpy())

# provide model parameters
# 大多数深度学习模型包含两种类型的输入：在推理期间保持固定的参数和
# 需要针对每个推理任务进行更改的数据输入。
d_graph, lib, params = nnvm.compiler.build(compute_graph, target='cuda',
                                           shape={'x': shape}, params={'y': y_np})

print('\n------optimized params----------')
print(params)
print('\n-------deploy library----------')
# sqrt在nnvm编译时已经被优化
print(lib.imported_modules[0].get_source())

# save model
# from tvm.contrib import util

path_lib = 'model/deploy.so'
lib.export_library(path_lib)
with open('model/deploy.json', 'w') as fo:
    fo.write(d_graph.json())
with open("model/deploy.params", "wb") as fo:
    fo.write(nnvm.compiler.save_param_dict(params))

loaded_lib = tvm.module.load(path_lib)
loaded_json = open("model/deploy.json", 'r').read()
loaded_params = bytearray(open("model/deploy.params", "rb").read())

module = graph_runtime.create(loaded_json, loaded_lib, tvm.gpu(0))
params = nnvm.compiler.load_param_dict(loaded_params)
module.load_params(loaded_params)
module.run(x=x_np)
out = module.get_output(0, out=tvm.nd.empty(shape))
print(out.asnumpy())