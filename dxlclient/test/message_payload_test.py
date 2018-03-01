from __future__ import absolute_import
from __future__ import print_function
from io import BytesIO
import time
from threading import Condition
from dxlclient import UuidGenerator, ServiceRegistrationInfo, RequestCallback, Request
from dxlclient.test.base_test import BaseClientTest
from dxlclient.test.test_service import TestService
from nose.plugins.attrib import attr
from dxlclient._vendor.msgpack.fallback import Unpacker
from dxlclient._vendor.msgpack.fallback import Packer


@attr('system')
class MessagePayloadTest(BaseClientTest):

    MAX_WAIT = 1 * 60
    # A test string to send
    TEST_STRING = "SslUtils"
    # A test byte to send
    TEST_BYTE = 1
    # A test integer
    TEST_INT = 123456

    request_received = None
    request_complete_condition = Condition()

    # Tests whether payloads can be successfully delivered from a client to the server.
    # Payloads are simply bytes of data that are used to provide application-specific
    # information.
    @attr('system')
    def test_execute_message_payload(self):

        # Create a server that handles a request, unpacks the payload, and
        # asserts that the information in the payload was delivered successfully.
        with self.create_client(max_retries=0) as server:
            test_service = TestService(server, 1)
            server.connect()
            topic = UuidGenerator.generate_id_as_string()
            reg_info = ServiceRegistrationInfo(server,
                                               "message_payload_runner_service")

            # callback definition
            def on_request(request):
                with self.request_complete_condition:
                    try:
                        self.request_received = request
                    except Exception as e:
                        print(e)
                    self.request_complete_condition.notify_all()

            request_callback = RequestCallback()
            request_callback.on_request = on_request
            reg_info.add_topic(topic, request_callback)
            # Register the service
            server.register_service_sync(reg_info, self.DEFAULT_TIMEOUT)

            with self.create_client() as client:
                client.connect()
                packer = Packer()

                # Send a request to the server with information contained
                # in the payload
                request = Request(destination_topic=topic)
                request.payload = packer.pack(self.TEST_STRING)
                request.payload += packer.pack(self.TEST_BYTE)
                request.payload += packer.pack(self.TEST_INT)
                client.async_request(request, request_callback)

                start = time.time()
                # Wait until the request has been processed
                with self.request_complete_condition:
                    while (time.time() - start < self.MAX_WAIT) and \
                            not self.request_received:
                        self.request_complete_condition.wait(self.MAX_WAIT)

                self.assertIsNotNone(self.request_received)
                unpacker = Unpacker(file_like=BytesIO(request.payload))
                self.assertEquals(next(unpacker).decode('utf8'),
                                  self.TEST_STRING)
                self.assertEquals(next(unpacker), self.TEST_BYTE)
                self.assertEquals(next(unpacker), self.TEST_INT)
