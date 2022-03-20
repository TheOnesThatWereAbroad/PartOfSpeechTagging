import numpy as np
import os
import glob
from urllib import request
import zipfile
from sklearn.preprocessing import LabelBinarizer


class NotAdaptedError(Exception):
    pass


class TextVectorizer:
    def __init__(
        self,
        glove_url="http://nlp.stanford.edu/data/glove.6B.zip",
        max_tokens=20000,
        embedding_dim=100,
        embedding_folder="glove",
    ):
        """
        This class parses the GloVe embeddings, the input documents are expected
        to be in the form of a list of lists.
        [["word1", "word2", ...], ["word1", "word2", ...], ...]

        Parameters
        ----------
        glove_url : The url of the GloVe embeddings.
        max_tokens : The maximum number of words in the vocabulary.
        embedding_dim : The dimension of the embeddings (pick one of 50, 100, 200, 300).
        embedding_folder : folder where the embedding will be downloaded
        """
        self.max_tokens = max_tokens
        self.embedding_dim = embedding_dim
        self.download_glove_if_needed(glove_url=glove_url, embedding_folder=embedding_folder)
        
        # create the vocabulary
        self.vocabulary = self.parse_glove(embedding_folder) 

    def download_glove_if_needed(self, glove_url, embedding_folder):
        """
        Downloads the glove embeddings from the internet
        
        Parameters
        ----------
        glove_url : The url of the GloVe embeddings.
        embedding_folder: folder where the embedding will be downloaded
        """
        # create embedding folder if it does not exist
        if not os.path.exists(embedding_folder):
            os.makedirs(embedding_folder)

        # extract the embedding if it is not extracted
        if not glob.glob(os.path.join(embedding_folder, "**/glove*.txt"), recursive=True):

            # download the embedding if it does not exist 
            embedding_zip = os.path.join(embedding_folder, glove_url.split("/")[-1])
            if not os.path.exists(embedding_zip):
                print("Downloading the GloVe embeddings...")
                request.urlretrieve(glove_url, embedding_zip)
                print("Successful download!")

            # extract the embedding
            print("Extracting the embeddings...")
            with zipfile.ZipFile(embedding_zip, "r") as zip_ref:
                zip_ref.extractall(embedding_folder)
                print("Successfully extracted the embeddings!")
            os.remove(embedding_zip)

    def parse_glove(self, embedding_folder):
        """
        Parses the GloVe embeddings from their files, filling the vocabulary.
        
        Parameters
        ----------
        embedding_folder : folder where the embedding files are stored
        
        Returns
        -------
        dictionary representing the vocabulary from the embeddings
        """
        vocabulary = {}
        embedding_file = os.path.join(embedding_folder, "glove.6B." + str(self.embedding_dim) + "d.txt")
        with open(embedding_file, encoding='utf8') as f:
            for line in f:
                word, coefs = line.split(maxsplit=1)
                coefs = np.fromstring(coefs, "f", sep=" ")
                vocabulary[word] = coefs
        return vocabulary

    def adapt(self, documents):
        """
        Computes the OOV words for a single data split, and adds them to the dictionary.
        
        Parameters
        ----------
        documents : The data split (might be training set, validation set, or test set).
        """
        # create a set containing words from the documents in a given data split
        words = {
            word for doc in documents for word in doc
        }  
        oov_words = words - self.vocabulary.keys()

        # add the OOV words to the vocabulary giving them a random encoding
        for word in oov_words:
            self.vocabulary[word] = np.random.uniform(-1, 1, size=self.embedding_dim)
        print(f"Generated embeddings for {len(oov_words)} OOV words.")

    def transform(self, documents):
        """
        Transform the data into the input structure for the training. This method should be used always after the adapt method.

        Parameters
        ----------
        documents : The data split (might be training set, validation set, or test set). 
        
        Returns
        -------
        Numpy array of shape (number of documents, number of words, embedding dimension)
        """
        return np.array([self._transform_document(document) for document in documents])

    def _transform_document(self, document):
        """
        Transforms a single document to the GloVe embedding
        
        Parameters
        ----------
        document : The document to be transformed.

        Returns
        -------
        Numpy array of shape (number of words, embedding dimension)
        """
        try:
            return np.array([self.vocabulary[word] for word in document])
        except KeyError:
            raise NotAdaptedError(
                f"The whole document is not in the vocabulary. Please adapt the vocabulary first."
            )


class TargetVectorizer:

    def __init__(self):
        """
        This class one-hot encodes the target documents, containing the POS tags.
        """
        self.vectorizer = LabelBinarizer()

    def adapt(self, targets):
        """
        Fits the vectorizer for the classes.

        Parameters
        ----------
        targets : The target tags for the dataset split given (it is a list of lists).
        """
        self.vectorizer.fit(
            [target for doc_targets in targets for target in doc_targets]
        )

    def get_classes(self):
        return self.vectorizer.classes_

    def transform(self, targets):
        """
        Performs the one-hot encoding for the dataset Ys, returning a list of encoded document tags.
        
        Parameters
        ----------
        targets : The target tags for the dataset split given (it is a list of lists).

        Returns
        -------
        Numpy array of shape (number of documents, numbero of tokens, number of classes)
        """
        if self.vectorizer.classes_.shape[0] == 0:
            raise NotAdaptedError(
                "The target vectorizer has not been adapted yet. Please adapt it first."
            )
        return np.array([self.vectorizer.transform(document) for document in targets])

    def inverse_transform(self, targets):
        """
        Performs the inverse one-hot encoding for the dataset Ys, returning a list of decoded document tags.
        """
        if self.vectorizer.classes_.shape[0] == 0:
            raise NotAdaptedError(
                "The target vectorizer has not been adapted yet. Please adapt it first."
            )
        return np.array([self.vectorizer.inverse_transform(document) for document in targets])


if __name__ == "__main__":
    # read data
    dataset_dir = os.path.join("data", "dependency_treebank")
    docs = os.listdir(dataset_dir)
    X = []
    y = []
    for doc in docs:
        doc_path = os.path.join(dataset_dir, doc)
        np_doc = np.loadtxt(doc_path, str, delimiter="\t")
        X.append(np_doc[:, 0])
        y.append(np_doc[:, 1])
    X, y = np.array(X), np.array(y)

    print("BEFORE VECTORIZING")
    print("First input data:")
    print(f"\tShape: {X[0].shape}")
    #print(f"\tInput: {X[0]}")
    print("First target data:")
    print(f"\tShape: {y[0].shape}")
    print(f"\tTarget: {y[0]}")

    # convert inputs to vector representation
    text_vectorizer = TextVectorizer(
        embedding_dim=50,
        embedding_folder=os.path.join(os.getcwd(), "embeddings")
    )
    text_vectorizer.adapt(X)
    X = text_vectorizer.transform(X)

    # convert targets to one-hot representation
    target_vectorizer = TargetVectorizer()
    target_vectorizer.adapt(y)  
    y = target_vectorizer.transform(y)
    
    print("\nAFTER VECTORIZING")
    print("First input data:")
    print(f"\tShape: {X[0].shape}")
    print(f"\tInput: {X[0]}")
    print("First target data:")
    print(f"\tShape: {y[0].shape}")
    print(f"\tTarget: {y[0]}")
    print(f"\tInverse transformed target: {target_vectorizer.inverse_transform(y)[0]}")
