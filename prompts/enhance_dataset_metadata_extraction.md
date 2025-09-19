# Enhance dataset metadata extraction

1. Let's create a unique ID for each extraction of (e.g. folder1/folder2/.../input_folder) using a timestamp (ingest-2025-09-19-XXXXXXXXXX-input_folder) and put all the output files and folders into the extraction folder named: (output folder defined in parameters)/(extraction ID)

2. now consider each folder contained the input_folder is a dataset and the dataset_name is the folder name (e.g. input_folder/dataset_name), for each dataset processed by the script, name the folder as follows : dataset-(dataset_name)

3. allow the user to optionally specify a particular list of datasets he wants to process (by default process all datasets in the input folder)

4. run this new process with input: data/01-Claims-Travel-Canada datasets: [NAME_25], "Customer 1", output folder: output

