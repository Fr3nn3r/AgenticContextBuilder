small fix: the image viewer use the screen space by default (optionally allow zoom in and out)

New requirements:

Let's design a new UI screen (New claim) at the top of the left panel allowing the user to create new claims (giving a name or claim ID) and to drag and drop / upload document in the UI. There should be a progress bar for the uplad and the file name and metadata should appear on the screen in a list per claim. The user should be allowed to create several claim with different documents.

when the user is done with adding document to the "virtual claims" he can run the pipeline for all the claims (it's ok to have just one claim, there should also be an option to add the documents to a common stash - dummy claim)
there should be realtime updates of the pipeline status for each document updated live on the screen.

when the process is complete the screen should display the detail of what happened during the execution. 
