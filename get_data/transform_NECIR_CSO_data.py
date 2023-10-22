import pandas as pd
import numpy as np
import datetime

if __name__ == '__main__':
	## Load the dataset, which is static
	data = pd.read_csv('../docs/data/NECIR_CSO_2011.csv')

	## Print a sample of the file as an example
	data.sample(n=10).to_csv('../docs/data/NECIR_CSO_2011_sample.csv', index=False)

	## Report last update
	with open('../docs/data/ts_update_NECIR_CSO.yml', 'w') as f:
		f.write('updated: '+str(datetime.datetime.now()).split('.')[0]+'\n')
