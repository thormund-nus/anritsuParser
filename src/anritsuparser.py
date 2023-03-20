#! /usr/bin/python3
"""
Anritsu Parser.

Test on MS2723B save files.
TODO: Move into single-module distribution if src-layout is unnecessary.
"""

import numpy as np
from typing import Optional
from pathlib import Path

class SpectrumData(object):

    def __init__(self, path: Path=None, data: bytes=None, parseAll: bool=False):
        """
        Import Spectrum Data as stored under the path.

        Searches for all files in folder `path` if parseAll is set to 
        true (functionality to be implemented); Otherwise just parses 
        single file as provided by path.
        """
        
        if path and data:
            raise Exception("Both data and path supplied. Choose either one or the other.")
        if data and parseAll:
            raise Exception()

        # initialise class properties
        self.path = None
        if isinstance(path, str):  # typecasting
            path = Path(path)

        if path:
            # From provided path, parse files located under path if dir, 
            # else parse as file
            self.path = path

            if not self.path.exists():
                raise ValueError()
            
            if parseAll and path.is_dir():
                if not path.is_dir():
                    raise ValueError("Path provided is not a directory!")
                else:
                    # To implement how to concat frequency sensibly
                    raise NotImplementedError()

            elif (not parseAll) and path.is_file():
                self.parsed_data = self.parseFile(path)
                try:
                    self.spectrum = self.parseSpectrum(self.parsed_data)
                except ValueError:
                    print("No Spectrum Found")
            else:
                raise ValueError("Path given conflicts with `parseAll`.")

        elif data:
            self.parsed_data = self.parseData(data)
            self.spectrum = self.parseSpectrum(self.parsed_data)

    def parseFile(self, path: Path):
        with open(path, mode = 'r') as f:  # ASCII vs Binary support?
            filedata = f.read()
        self.parsed_data = self.parseData(filedata)
        return self.parsed_data

    def parseData(self, data: str):
        """
        This function will nest the file data into a nested dictionary structure.
        Some assumptions were made during it's creation.
        """

        data = data.split('\n')
        def append(result, key, value, level):
            """Modify result dictionary with degree of nesting dictated by level.
            
            Parameters
            ----------
            result : dict
                Eventual result released from parse_data function, which is 
                iteratively built up upon line by line.
            key, value : str, str
                key value pair intended for the result dictionary.
            level : int
                denotes the extent of nesting expected
            """
            if level < 0:
                raise ValueError("There is no level of nesting lower than 0")
            elif level==0:
                result[key] = value
            else:
                # assumes that keys are provided in order of provision (python 3.7)
                append(result[list(result.keys())[-1]],key,value, level-1)

        # intialisation
        result = {}
        lvl = 0 # degree of nesting
        i = 0 # line number

        while i < len(data): 
            line = data[i]

            # A line beginning with `#`` signifies some traversal in the nested
            #  dictionary
            if line.startswith('# ') and line.endswith('Done'):
                # `# ... Done` <- signifies the exit of a nested dictionary
                # Only `# ....\n<...>` consecutive lines are  allowed to 
                # create level 0 nested dicts
                lvl = max(lvl - 1, 1)
                # Remove max against 1 if decrement to 0 is instead preferred.

            elif line.startswith("# "):
                if i != len(data) and data[i+1].startswith("<") and data[i+1].endswith(">"):
                    # `#....\n<...>` consecutive lines are creates level 0 
                    # nested dictionary
                    lvl = 0
                    i += 1 # Line with <...> can be ignored
                append(result, line.strip("# ").strip("Begin "), {}, lvl)
                lvl += 1

            elif line.count("=")==1:
                # This line is not concerned with traversal of the nested 
                # dictionary, just populating the final result
                append(result, *line.split("="), lvl)
            
            # Increment line number
            i += 1

        # cleanup of level 0 nesting
        tmp_keys = [k for k, v in result.items() if v == {}]
        for k in tmp_keys:
            del result[k]
            
        # compress first level key value pairs into a metadata key
        tmp_keys = [k for k, v in result.items() if isinstance(v, str)]
        tmp_dict = {}
        for k in tmp_keys:
            tmp_dict[k] = result[k]
            del result[k]
        result['METADATA'] = tmp_dict

        #reorder metadata as being the first key
        desired_key_order = ['METADATA'] + list(result.keys())[:-1]
        result = {k: result[k] for k in desired_key_order}
        return result

    def parseSpectrum(self, parsed_data: dict):
        """Obtains numpy 2D array of (freq, power)

        Does a key search to see if some nested dictionary contains keys
        of only form "P_<int>". Afterwards, yield for spectrum.

        Parameters
        ----------
        parsed_data : dict
            Nested dictionary format of raw data, as obtained from 
            parseData/parseFile method.
        """
        def search(nested_dict: dict) -> Optional[np.array]:
            """Recursive depth-frist search on parsed_data dictionary for
            spectrum data."""
            keys = nested_dict.keys()
            ascii_int = lambda c: 48 <= ord(c) <= 57
            p_int = lambda x: x.startswith('P_') and all(map(ascii_int, x[2:]))
            if all(map(p_int, keys)) and len(keys) > 0:
                # dict key has been hit! time to return the numpy array
                # fromiter only supports 1D arrays
                # def get_y(dict_values: str):
                #     return dict_values.split(' , ')[0]
                # def get_x(dict_values: str):
                #     return dict_values.split(' , ')[1].split(' ')[0] # removes units
                get_y = lambda dict_values: dict_values.split(' , ')[0]
                get_x = lambda dict_values: dict_values.split(' , ')[1].split(' ')[0]

                # nested_dict['P_0'] = '<power>, <freq> MHz'
                x = np.fromiter(map(get_x, nested_dict.values()), dtype=np.double)
                y = np.fromiter(map(get_y, nested_dict.values()), dtype=np.double)
                return np.vstack((x, y))

            # key has not been hit, continue with DFS.
            for k in keys.__reversed__():  # reversed for attempted optimization
                if isinstance(nested_dict[k], dict):
                    return search(nested_dict[k])
            return None

        if isinstance(result := search(parsed_data), np.ndarray):
            return result
        raise ValueError("Spectrum could not be found!")

    def __repr__(self):
        string = "Anritsu Spectrum Data\n" + '-'*21 
        if 'path' in self.__dict__.keys():
            string += "\nPath: " + str(self.path)
        if 'parsed_data' in self.__dict__.keys():
            string += '\n' + "\n".join([f"{k}: {v}" for k, v in self.parsed_data["METADATA"].items()])

        return string
