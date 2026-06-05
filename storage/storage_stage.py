from __future__ import annotations

from core.frame_packet import FramePacket
from storage.files import FileStorage
from storage.repository import TrackResultRecord, TrackResultRepository

class StorageStage:
    name = "storage"

    def __init__(
        self,
        run_id: int,
        file_storage: FileStorage,
        repository: TrackResultRepository,
        save_only_confirmed: bool = True,
        clear_crop_after_save: bool = True,
    ) -> None:
        self.run_id = run_id
        self.file_storage = file_storage
        self.repository = repository
        self.save_only_confirmed = save_only_confirmed
        self.clear_crop_after_save = clear_crop_after_save


    def __call__(self, packet: FramePacket) -> FramePacket:
        saved_events = []

        # print(f"[storage] got {len(packet.lost_tracks)} lost tracks on frame {packet.frame_id}") # отладочная информация

        for event in packet.lost_tracks:

            # print(
            # f"[storage] event track_id={event.get('track_id')} " # отладочная информация
            # f"confirmed={event.get('confirmed')} " # отладочная информация
            # f"best_frame_id={event.get('best_frame_id')} " # отладочная информация
            # f"has_crop={event.get('best_crop') is not None}" # отладочная информация
            # )

            confirmed = bool(event.get("confirmed", False))
            if self.save_only_confirmed and not confirmed:
                continue

            crop = event.get("best_crop")
            crop_path = None
            crop_width = None
            crop_height = None

            if crop is not None:
                crop_height, crop_width = crop.shape[:2]
                crop_path = self.file_storage.save_track_crop(
                    crop=crop,
                    run_id=self.run_id,
                    track_id=int(event["track_id"]),
                    class_name=str(event.get("class_name", "unknown")),
                    frame_id=event.get("best_frame_id"),
                )
                print(f"[storage] crop saved: {crop_path}") # отладочная информация
            best_bbox_raw = event.get("best_bbox")
            best_bbox = tuple(best_bbox_raw) if best_bbox_raw is not None else None
            last_bbox = tuple(event["last_bbox"])

            record = TrackResultRecord(
                run_id=self.run_id,
                track_id=int(event["track_id"]),
                class_id=int(event.get("class_id", -1)),
                class_name=str(event.get("class_name", "unknown")),
                last_bbox=last_bbox,
                best_bbox=best_bbox,
                best_confidence=float(event.get("best_confidence", 0.0)),
                best_frame_id=event.get("best_frame_id"),
                last_seen_frame=int(event.get("last_seen_frame", packet.frame_id)),
                age=int(event.get("age", 0)),
                confirmed=confirmed,
                crop_path=crop_path,
                crop_width=crop_width,
                crop_height=crop_height,
            )
            self.repository.save_track_result(record)
            
            # print(            
            # f"[storage] db saved: run_id={record.run_id} " # отладочная информация
            # f"track_id={record.track_id} crop_path={record.crop_path}" # отладочная информация  
            # ) # отладочная информация

            event["storage_saved"] = True
            event["crop_path"] = crop_path
            event["crop_width"] = crop_width
            event["crop_height"] = crop_height

            if self.clear_crop_after_save and "best_crop" in event:
                event["best_crop"] = None

            saved_events.append(event)
        
        # print(f"[storage] saved {len(saved_events)} events") # отладочная информация

        packet.meta["storage_saved_events"] = saved_events
        return packet