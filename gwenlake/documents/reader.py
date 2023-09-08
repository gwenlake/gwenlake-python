from gwenlake.api import APIClient



class DocumentTextReader:

    def __init__(self, file):
        try:
            files = {'file': (file, open(file,'rb'))}
            self.content = APIClient().fetch(f"/documents/readtext", files=files, method="post")
        except Exception as e:
            print(e)
    
    def get_content(self):
        return self.content
