import inspect
import imp
import sys , os
if len(sys.argv) < 2:
	print "need a few files to inspect :)"
	exit(-1)
	
	
else:
	for i in sys.argv[1:]:
		path = os.path.abspath ( i )
		print ("inspecting --> %s" % os.path.split(path)[1])
		def scoped(path):
			exec(open(path).read())
			mem = locals()
			vals = {}
			for i in mem:
				if callable(mem[i]) and hasattr(mem[i],"wrapped"):
					vals[i]=mem[i]
			sorted_keys = vals.keys()
			sorted_keys.sort()
			
			print("functions listed %s" % ",".join( sorted_keys ))
			for i in sorted_keys:
				wrapped = vals[i]
				while hasattr(wrapped,'wrapped'):
					wrapped = getattr(wrapped,'wrapped')
				spec = inspect.getargspec(wrapped)
				str = inspect.formatargspec(spec.args, spec.varargs, spec.keywords, spec.defaults)
				print ("\t.. autofunction:: %s %s" % (i, str))

		scoped(path)