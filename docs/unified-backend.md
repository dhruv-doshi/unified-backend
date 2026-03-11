Added the backend requirements from the Image Analysis app in the ./backend-requirement.md file. Follow this and build the backend. 

- Create a python virtual environemt for this project and use all files in that. Save all models in a local cache within this folder if that is possible so when this folder is cleaned, all the models are also cleaned up easily. 
- Remember this is the requirements only from one particular app, there are many other apps that will be using this backend service. 
- Ensure all proper test cases, code quality checks and documentation is done correctly. 
- Use the api paths are the best suited as per the backend standards already set in the claude skills. Whatever differences are made in contrast to the requirements given, you can give a counter document which can be used to modify the frontend. This is important as we are using one backend and it is easier for all the frontend to maintain their code in accordance to the backend standards. 
- Write the API paths in such a way that they are modular. For example, the authentication can be common for all, one user to be created for all the different apps that are to be built by me. 
- For routes that use LLM calls, we can have separate mapping for the app vs LLM to use, for example, if the LLM call is from the image analysis app and it is to analyse a particular image, then we make use of Nano Banana Pro. Such mappings will help us keep only a single route and based on the requirement, we can adjust the payload and send it to the required LLM through open router or ollama. 
- In a scenario a LLM has to be used locally, then it is very crucial to ensure all this is properly downloaded at the start of the server to ensure smooth service. 
- Build this backend incrementaly, test what is built, ensure the code quality and keep updating the docs 
- Finally, give what all updates are need to be made in the frontend. Remember, the backend decides the API format and not the frontend. 