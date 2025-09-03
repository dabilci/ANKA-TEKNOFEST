import React, { memo, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import TurkeySvgMap from "turkey-map-react";
import "./TurkeyMap.css";

const TurkeyMap = () => {
  const navigate = useNavigate();

  const handleClick = (city) => {
    const provinceName = city?.name;
    if (provinceName) {
      navigate(`/il/${encodeURIComponent(provinceName)}`);
    }
  };

  const CityWithLabel = ({ cityComponent, cityData }) => {
    const pathRef = useRef(null);
    const [labelPos, setLabelPos] = useState(null);

    useEffect(() => {
      if (pathRef.current && typeof pathRef.current.getBBox === "function") {
        const bbox = pathRef.current.getBBox();
        setLabelPos({ x: bbox.x + bbox.width / 2, y: bbox.y + bbox.height / 2 });
      }
    }, []);

    const cloned = React.cloneElement(cityComponent, { ref: pathRef });

    return (
      <g>
        {cloned}
        {labelPos && (
          <text
            className="province-label"
            x={labelPos.x}
            y={labelPos.y}
          >
            {cityData?.name}
          </text>
        )}
      </g>
    );
  };

  const renderCity = (cityComponent, cityData) => (
    <CityWithLabel key={cityData?.id} cityComponent={cityComponent} cityData={cityData} />
  );

  return (
    <div className="map-container">
      <TurkeySvgMap onClick={handleClick} cityWrapper={renderCity} />
    </div>
  );
};

export default memo(TurkeyMap);
