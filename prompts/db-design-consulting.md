I must now thing about how to store my data in a supabase database. I want to store document/metadata/extracted content in the backend database. I am wondering a few thing: 1. where should I maintain by database schema/scripts, I want the simplest method possible, I'm not epxecting changes very often but still I want a clean and lean process to upgrade the DB especially in developement, it is still ok to drop the DB completely for now. 2. I'm a wondering what the DB schema should look like, I'm going to have users but no multi-tenancy issue, I'd like to have google aithentication but I've run into so many issue with goole auth I find it complicated maybe email is ok to start from. Help me adderss the key considerations.

I want to treat each file as its own piece of content. 


Then in the UI I later on I will have 2 main capabilities: 
1. browse/view dataset and documents -> extracted data and metadata compare against golden standards and evaluate fields summaries, classifications etc... so it is essentially an evaluation UI also with the ability to TAG/Add metadata to documents and elements of the context
2. run a chatbot against configurable context with dummy tools