import cv2
import numpy as np
import time
import random
from PIL import Image
import imutils
import sys
import urllib
import os
from adapt.intent import IntentBuilder
from mycroft.skills.core import MycroftSkill
from mycroft.messagebus.message import Message

from imgurpython import ImgurClient

__author__ = 'jarbas'


class DreamService(MycroftSkill):

    def __init__(self):
        super(DreamService, self).__init__(name="DreamSkill")
        self.reload_skill = False

        # TODO get from config
        try:
            client_id = self.config_core.get("APIS")["ImgurKey"]
            client_secret = self.config_core.get("APIS")["ImgurSecret"]
        except:
            try:
                client_id = self.config.get("ImgurKey")
                client_secret = self.config.get("ImgurSecret")
            except:
                # TODO throw error
                client_id = 'xx'
                client_secret = 'yyyyyyyyy'

        self.client = ImgurClient(client_id, client_secret)

        try:
            path = self.config["caffe_path"]
        except:
            path = "../caffe"

        sys.path.insert(0, path + '/python')
        from batcountry import BatCountry

        self.model = "bvlc_googlenet"
        path += '/models/' + self.model

        # start batcountry instance (self, base_path, deploy_path=None, model_path=None,
        self.bc = BatCountry(path)#path,model_path=path)
        self.iter = 25#20#self.config["iter"] #dreaming iterations
        self.layers = [ "inception_5b/output", "inception_5b/pool_proj",
                        "inception_5b/pool", "inception_5b/5x5",
                        "inception_5b/5x5_reduce", "inception_5b/3x3",
                        "inception_5b/3x3_reduce", "inception_5b/1x1",
                        "inception_5a/output", "inception_5a/pool_proj",
                        "inception_5a/pool", "inception_5a/5x5",
                        "inception_5a/5x5_reduce", "inception_5a/3x3",
                        "inception_5a/3x3_reduce", "inception_5a/1x1",
                        "pool4/3x3_s2", "inception_4e/output", "inception_4e/pool_proj",
                        "inception_4e/pool", "inception_4e/5x5",
                        "inception_4e/5x5_reduce", "inception_4e/3x3",
                        "inception_4e/3x3_reduce", "inception_4e/1x1",
                        "inception_4d/output", "inception_4d/pool_proj",
                        "inception_4d/pool", "inception_4d/5x5",
                        "inception_4d/5x5_reduce", "inception_4d/3x3",
                        "inception_4d/3x3_reduce", "inception_4d/1x1",
                        "inception_4c/output", "inception_4c/pool_proj",
                        "inception_4c/pool", "inception_4c/5x5",
                        "inception_4c/5x5_reduce", "inception_4c/3x3",
                        "inception_4c/3x3_reduce", "inception_4c/1x1",
                        "inception_4b/output", "inception_4b/pool_proj",
                        "inception_4b/pool", "inception_4b/5x5",
                        "inception_4b/5x5_reduce", "inception_4b/3x3",
                        "inception_4b/3x3_reduce", "inception_4b/1x1",
                        "inception_4a/output", "inception_4a/pool_proj",
                        "inception_4a/pool", "inception_4a/5x5",
                        "inception_4a/5x5_reduce", "inception_4a/3x3",
                        "inception_4a/3x3_reduce", "inception_4a/1x1",
                        "inception_3b/output", "inception_3b/pool_proj",
                        "inception_3b/pool", "inception_3b/5x5",
                        "inception_3b/5x5_reduce", "inception_3b/3x3",
                        "inception_3b/3x3_reduce", "inception_3b/1x1",
                        "inception_3a/output", "inception_3a/pool_proj",
                        "inception_3a/pool", "inception_3a/5x5",
                        "inception_3a/5x5_reduce", "inception_3a/3x3",
                        "inception_3a/3x3_reduce", "inception_3a/1x1",
                        "pool2/3x3_s2","conv2/norm2","conv2/3x3",
                        "conv2/3x3_reduce", "pool1/norm1"] #"pool1/3x3_s2" , "conv17x7_s2"

        ###imagine dimensions
        self.w = 640
        self.h = 480

        ### flag to avoid dreaming multiple times at once
        self.dreaming = False

        self.outputdir = self.config_core["database_path"] + "/dreams/"

        # check if folders exist
        if not os.path.exists(self.outputdir):
            os.makedirs(self.outputdir)

    def initialize(self):
        self.emitter.on("deep_dream_request", self.handle_dream)

        dream_status_intent = IntentBuilder("DreamStatusIntent") \
            .require("dream").build()
        self.register_intent(dream_status_intent,
                             self.handle_dream_status_intent)

    def handle_dream_status_intent(self, message):
        self.speak_dialog("dreamstatus")

    def handle_dream(self, message):
        # TODO dreaming queue
        source = message.data.get("dream_source")
        guide = message.data.get("dream_guide")
        name = message.data.get("dream_name")
        user_id = message.data.get("source")

        if user_id is not None:
            if user_id == "unknown":
                user_id = "all"
            self.target = user_id
        else:
            self.log.warning("no user/target specified")
            user_id = "all"

        if name is None:
            name = time.asctime().replace(" ","_") + ".jpg"

        if guide is not None:
            result = self.guided_dream(source, guide, name)
        else:
            result = self.dream(source, name)

        print result
        if result is not None:
            data = self.client.upload_from_path(result)
            link = data["link"]
            self.speak("Here is what i dreamed", metadata={"dream_url": link})
            self.emitter.emit(Message("message_request", {"user_id":user_id, "data":{"dream_url":link}, "type":"deep_dream_result"}))

    #### dreaming functions
    def dream(self, imagepah, name):
        self.speak("please wait while the dream is processed")

        layer = random.choice(self.layers)

        req = urllib.urlopen(imagepah)
        arr = np.asarray(bytearray(req.read()), dtype=np.uint8)
        img = cv2.imdecode(arr, -1)  # 'load it as it is'
        dreampic = imutils.resize(img, self.w, self.h)  # cv2.resize(img, (640, 480))
        image = self.bc.dream(np.float32(dreampic), end=layer, iter_n=int(self.iter))
        # write the output image to file
        result = Image.fromarray(np.uint8(image))
        outpath = self.outputdir + name
        result.save(outpath)
        return outpath

    def guided_dream(self, sourcepath, guidepath, name):
        pass

    def stop(self):
        try:
            self.bc.cleanup()
            cv2.destroyAllWindows()
        except:
            pass


def create_skill():
    return DreamService()