import web

import types


def get_all_functions(module):
	functions = {}
	for f in [module.__dict__.get(a) for a in dir(module)
		if isinstance(module.__dict__.get(a), types.FunctionType)]:
			functions[f.__name__] = f
	return functions
